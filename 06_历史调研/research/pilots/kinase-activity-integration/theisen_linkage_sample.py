"""Select a fixed stratified sample and crosswalk it to the live ChEMBL API.

Selection is deterministic and case-sensitive. The manifest is written before
any ChEMBL lookup, to avoid choosing rows based on whether they match.
Python standard library only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "reproductions" / "kinase-activity-integration" / "data" / "prepped_activities_all_chembl_pubchem.csv"
OUT_DIR = Path(__file__).resolve().parent
BASE = "https://www.ebi.ac.uk/chembl/api/data"
TIMEOUT = 45


def get_json(resource: str, params: dict[str, str] | None = None) -> dict:
    url = f"{BASE}/{resource}.json"
    if params:
        url += "?" + urlencode(params)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "JanusDatasetResearch/1.0"})
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with urlopen(request, timeout=TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                break
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET failed: {url}: {last_error}")


def get_all_activities(molecule_id: str) -> list[dict]:
    params = {"molecule_chembl_id": molecule_id, "limit": "1000", "offset": "0"}
    data = get_json("activity", params)
    activities = list(data.get("activities", []))
    page_meta = data.get("page_meta") or {}
    total = page_meta.get("total_count", len(activities))
    offset = len(activities)
    while offset < total:
        params["offset"] = str(offset)
        page = get_json("activity", params)
        new_activities = page.get("activities", [])
        if not new_activities:
            break
        activities.extend(new_activities)
        offset += len(new_activities)
    return activities


def select_rows(n_per_stratum: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with SOURCE.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row["activity_type"] != "measured":
                continue
            row["pactivity_stratum"] = "le_6" if float(row["activity_value"]) <= 6 else "gt_6"
            # Exact input fields, including SMILES case, define both key and hash.
            key = "\0".join((row["canonical_smiles"], row["uniprot_id"], row["activity_value"]))
            row["selection_sha256"] = hashlib.sha256(key.encode("utf-8")).hexdigest()
            rows.append(row)
    chosen: list[dict[str, str]] = []
    for stratum in ("le_6", "gt_6"):
        pool = [row for row in rows if row["pactivity_stratum"] == stratum]
        chosen.extend(sorted(pool, key=lambda row: row["selection_sha256"])[:n_per_stratum])
    return sorted(chosen, key=lambda row: (row["pactivity_stratum"], row["selection_sha256"]))


def save_manifest(rows: list[dict[str, str]], destination: Path) -> None:
    fields = ["source_row", "canonical_smiles", "uniprot_id", "activity_value", "pactivity_stratum", "selection_sha256", "ck_split_set", "ligand_split_set", "cluster_split_set"]
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({"source_row": row["Unnamed: 0"], **{key: row[key] for key in fields[1:]}})


def result_for(row: dict[str, str]) -> dict[str, str]:
    result = {
        "source_row": row["source_row"], "canonical_smiles": row["canonical_smiles"],
        "uniprot_id": row["uniprot_id"], "prepared_pactivity": row["activity_value"],
        "stratum": row["pactivity_stratum"], "selection_sha256": row["selection_sha256"],
        "match_class": "", "chembl_molecule_ids": "", "exact_smiles_molecule_ids": "",
        "structure_match_level": "connectivity search only; stereochemical identity not independently verified",
        "target_ids": "", "activity_ids": "", "standard_types": "", "standard_relations": "",
        "standard_values": "", "standard_units": "", "pchembl_values": "",
        "assay_ids": "", "assay_descriptions": "", "document_ids": "", "dois": "",
        "exact_value_activity_ids": "", "api_db_version": "", "error": "",
        "document_titles": "", "dois": "", "journal_years": "", "assay_descriptions": "",
        "assay_target_ids": "", "assay_formats": "", "_activity_records": [],
    }
    try:
        mol_data = get_json("molecule", {"molecule_structures__canonical_smiles__connectivity": row["canonical_smiles"], "limit": "100"})
        molecules = mol_data.get("molecules", [])
        molecule_ids = sorted({m["molecule_chembl_id"] for m in molecules if m.get("molecule_chembl_id")})
        result["chembl_molecule_ids"] = ";".join(molecule_ids)

        target_data = get_json("target", {"target_components__accession": row["uniprot_id"], "limit": "100"})
        targets = []
        for target in target_data.get("targets", []):
            accessions = {component.get("accession") for component in target.get("target_components", [])}
            if row["uniprot_id"] in accessions and target.get("target_chembl_id"):
                targets.append(target)
        target_ids = sorted({target["target_chembl_id"] for target in targets})
        result["target_ids"] = ";".join(target_ids)
        target_by_id = {target["target_chembl_id"]: target for target in targets if target.get("target_chembl_id")}

        activities: list[dict] = []
        # The API query is explicitly a connectivity search. Retain that scope:
        # do not promote a candidate to exact stereochemical identity.
        for molecule_id in molecule_ids:
            for activity in get_all_activities(molecule_id):
                if activity.get("target_chembl_id") in target_ids:
                    activities.append(activity)

        if not molecule_ids:
            result["match_class"] = "no_exact_connectivity_hit_current_ChEMBL" if molecule_ids else "no_structure_candidate_current_ChEMBL"
        elif not target_ids:
            result["match_class"] = "connectivity_candidate_but_target_accession_unresolved"
        elif not activities:
            result["match_class"] = "connectivity_candidate_and_target_but_no_pair_activity_returned"
        else:
            result["match_class"] = "pair_activity_found_no_exact_pchembl_match"

        values = []
        exact_value_ids = []
        for activity in activities:
            value = activity.get("pchembl_value")
            try:
                close = abs(float(value) - float(row["activity_value"])) <= 0.005
            except (TypeError, ValueError):
                close = False
            if close:
                exact_value_ids.append(activity.get("activity_id", ""))
            values.append(activity)
        result["_activity_records"] = [
            {
                "source_row": row["source_row"], "stratum": row["pactivity_stratum"],
                "prepared_pactivity": row["activity_value"], "canonical_smiles": row["canonical_smiles"],
                "uniprot_id": row["uniprot_id"], "molecule_chembl_id": activity.get("molecule_chembl_id", ""),
                "target_chembl_id": activity.get("target_chembl_id", ""),
                "target_pref_name": (target_by_id.get(activity.get("target_chembl_id")) or {}).get("pref_name", ""),
                "target_type": (target_by_id.get(activity.get("target_chembl_id")) or {}).get("target_type", ""),
                "activity_id": activity.get("activity_id", ""), "standard_type": activity.get("standard_type", ""),
                "standard_relation": activity.get("standard_relation", ""), "standard_value": activity.get("standard_value", ""),
                "standard_units": activity.get("standard_units", ""), "pchembl_value": activity.get("pchembl_value", ""),
                "assay_chembl_id": activity.get("assay_chembl_id", ""),
                "document_chembl_id": activity.get("document_chembl_id", ""),
                "prepared_pchembl_match": str(activity.get("activity_id", "") in exact_value_ids).lower(),
            }
            for activity in values
        ]
        if exact_value_ids:
            result["match_class"] = "connectivity_level_pchembl_match_stereo_unresolved_unique_record" if len(exact_value_ids) == 1 else "connectivity_level_pchembl_match_stereo_unresolved_multiple_records"
        result["exact_value_activity_ids"] = ";".join(sorted(str(value) for value in exact_value_ids if value))
        for output, field in (("activity_ids", "activity_id"), ("standard_types", "standard_type"), ("standard_relations", "standard_relation"), ("standard_values", "standard_value"), ("standard_units", "standard_units"), ("pchembl_values", "pchembl_value"), ("assay_ids", "assay_chembl_id"), ("document_ids", "document_chembl_id")):
            result[output] = " | ".join(sorted({str(a.get(field) or "") for a in values if a.get(field) is not None}))
        return result
    except Exception as error:  # retain sample row even for transient lookup failure
        result["match_class"] = "api_error_or_unresolved"
        result["error"] = str(error)
        return result


def get_detail(resource: str, field: str, identifier: str) -> dict:
    data = get_json(resource, {field: identifier, "limit": "1"})
    plural = {"document": "documents", "assay": "assays"}[resource]
    records = data.get(plural, [])
    return records[0] if records else {}


def enrich_source_context(rows: list[dict[str, str]]) -> None:
    activities = [activity for row in rows for activity in row.get("_activity_records", [])]
    document_ids = sorted({str(activity.get("document_chembl_id")) for activity in activities if activity.get("document_chembl_id")})
    assay_ids = sorted({str(activity.get("assay_chembl_id")) for activity in activities if activity.get("assay_chembl_id")})
    details: dict[tuple[str, str], dict] = {}
    work = [("document", "document_chembl_id", value) for value in document_ids]
    work += [("assay", "assay_chembl_id", value) for value in assay_ids]
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = {executor.submit(get_detail, resource, field, identifier): (resource, identifier) for resource, field, identifier in work}
        for future in as_completed(futures):
            resource, identifier = futures[future]
            try:
                details[(resource, identifier)] = future.result()
            except Exception as error:
                details[(resource, identifier)] = {"lookup_error": str(error)}
    for row in rows:
        row_activities = row.get("_activity_records", [])
        docs = [details.get(("document", value), {}) for value in row["document_ids"].split(" | ") if value]
        assays = [details.get(("assay", value), {}) for value in row["assay_ids"].split(" | ") if value]
        row["document_titles"] = " | ".join(sorted({str(doc.get("title") or "") for doc in docs if doc.get("title")}))
        row["dois"] = " | ".join(sorted({str(doc.get("doi") or "") for doc in docs if doc.get("doi")}))
        row["journal_years"] = " | ".join(sorted({" ".join(str(doc.get(key) or "") for key in ("journal", "year")).strip() for doc in docs if doc.get("journal") or doc.get("year")}))
        row["assay_descriptions"] = " | ".join(sorted({str(assay.get("description") or "") for assay in assays if assay.get("description")}))
        row["assay_target_ids"] = " | ".join(sorted({str(assay.get("target_chembl_id") or "") for assay in assays if assay.get("target_chembl_id")}))
        row["assay_formats"] = " | ".join(sorted({str(assay.get("bao_label") or assay.get("assay_type_description") or "") for assay in assays if assay.get("bao_label") or assay.get("assay_type_description")}))
        for activity in row_activities:
            doc = details.get(("document", str(activity.get("document_chembl_id"))), {})
            assay = details.get(("assay", str(activity.get("assay_chembl_id"))), {})
            activity["document_title"] = doc.get("title", "")
            activity["doi"] = doc.get("doi", "")
            activity["journal"] = doc.get("journal", "")
            activity["year"] = doc.get("year", "")
            activity["assay_description"] = assay.get("description", "")
            activity["assay_format"] = assay.get("bao_label") or assay.get("assay_type_description", "")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--select", action="store_true", help="write the deterministic manifest only")
    parser.add_argument("--n-per-stratum", type=int, default=10)
    parser.add_argument("--output-prefix", default="theisen_linkage_sample", help="distinct artifact prefix; existing outputs are not overwritten unless the same prefix is reused")
    args = parser.parse_args()
    manifest_path = OUT_DIR / f"{args.output_prefix}_manifest.csv"
    results_path = OUT_DIR / f"{args.output_prefix}_results.csv"
    activity_records_path = OUT_DIR / f"{args.output_prefix}_activity_records.csv"
    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)
    if args.select or not manifest_path.is_file():
        selected = select_rows(args.n_per_stratum)
        save_manifest(selected, manifest_path)
        print(f"Wrote fixed manifest first: {manifest_path} ({len(selected)} rows)")
        if args.select:
            return
    with manifest_path.open("r", newline="", encoding="utf-8-sig") as handle:
        manifest_rows = list(csv.DictReader(handle))
    status = get_json("status")
    status_obj = status
    db_version = str(status_obj.get("chembl_db_version") or status_obj.get("db_version") or "")
    print(f"ChEMBL status response: {json.dumps(status_obj, ensure_ascii=False)}")
    completed: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(result_for, row): row["source_row"] for row in manifest_rows}
        for future in as_completed(futures):
            record = future.result()
            record["api_db_version"] = db_version
            completed.append(record)
            print(f"Finished source row {record['source_row']}: {record['match_class']}", flush=True)
    completed.sort(key=lambda record: int(record["source_row"]))
    enrich_source_context(completed)
    activity_rows = [activity for row in completed for activity in row.pop("_activity_records", [])]
    activity_rows.sort(key=lambda row: (int(row["source_row"]), str(row["activity_id"])))
    activity_fields = ["source_row", "stratum", "prepared_pactivity", "uniprot_id", "canonical_smiles", "molecule_chembl_id", "target_chembl_id", "target_pref_name", "target_type", "activity_id", "standard_type", "standard_relation", "standard_value", "standard_units", "pchembl_value", "prepared_pchembl_match", "assay_chembl_id", "assay_description", "assay_format", "document_chembl_id", "document_title", "doi", "journal", "year"]
    with activity_records_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=activity_fields)
        writer.writeheader()
        writer.writerows(activity_rows)
    fields = list(completed[0]) if completed else []
    with results_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(completed)
    print(f"Wrote results: {results_path} ({len(completed)} rows)")
    print(f"Wrote activity-level context: {activity_records_path} ({len(activity_rows)} rows)")


if __name__ == "__main__":
    main()
