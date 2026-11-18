"""Retrieve NCBI identities for all accessioned proteins in the GH1 core pool.

Non-accessioned source labels (for example CR_14_Cow_Rumen) are retained with
an explicit unresolved status; they are not coerced into fake accessions.
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
POOL = HERE / "gh1_nims_candidate_pool_1803.csv"
OUTPUT = HERE / "gh1_nims_core96_ncbi_crosswalk.csv"
NCBI_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
ACCESSION_PATTERN = re.compile(r"^([A-Z]{1,4}\d+\.\d+)_")
CHUNK_SIZE = 10


def accession_from_label(label: str) -> str:
    match = ACCESSION_PATTERN.match(label)
    return match.group(1) if match else ""


def fetch_genbank(accessions: list[str]) -> str:
    params = urlencode(
        {
            "db": "protein",
            "id": ",".join(accessions),
            "rettype": "gb",
            "retmode": "text",
        }
    )
    request = Request(
        f"{NCBI_URL}?{params}",
        headers={"User-Agent": "Janus-Dataset research audit/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            with urlopen(request, timeout=90) as response:
                if response.status != 200:
                    raise RuntimeError(f"NCBI returned HTTP {response.status}")
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:  # Preserve a bounded retry for transient truncated responses.
            last_error = error
            if attempt < 4:
                delay = attempt * 2
                print(f"NCBI request failed (attempt {attempt}/4); retrying in {delay}s: {error}")
                time.sleep(delay)
    assert last_error is not None
    raise last_error


def fetch_fasta(accessions: list[str]) -> str:
    params = urlencode(
        {
            "db": "protein",
            "id": ",".join(accessions),
            "rettype": "fasta",
            "retmode": "text",
        }
    )
    request = Request(
        f"{NCBI_URL}?{params}",
        headers={"User-Agent": "Janus-Dataset research audit/1.0"},
    )
    last_error: Exception | None = None
    for attempt in range(1, 5):
        try:
            with urlopen(request, timeout=90) as response:
                if response.status != 200:
                    raise RuntimeError(f"NCBI returned HTTP {response.status}")
                return response.read().decode("utf-8", errors="replace")
        except Exception as error:
            last_error = error
            if attempt < 4:
                delay = attempt * 2
                print(f"NCBI FASTA request failed (attempt {attempt}/4); retrying in {delay}s: {error}")
                time.sleep(delay)
    assert last_error is not None
    raise last_error


def parse_fasta(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    header = ""
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if header:
                match = re.search(r"([A-Z]{1,4}\d+\.\d+)", header)
                if match:
                    result[match.group(1)] = "".join(chunks).upper()
            header = line[1:]
            chunks = []
        elif header:
            chunks.append(re.sub(r"\s+", "", line))
    if header:
        match = re.search(r"([A-Z]{1,4}\d+\.\d+)", header)
        if match:
            result[match.group(1)] = "".join(chunks).upper()
    return result


def parse_records(text: str) -> dict[str, dict[str, str]]:
    parsed: dict[str, dict[str, str]] = {}
    for block in text.split("//"):
        if "LOCUS" not in block or "ACCESSION" not in block:
            continue
        version_match = re.search(r"^VERSION\s+(\S+)", block, re.MULTILINE)
        accession_match = re.search(r"^ACCESSION\s+(\S+)", block, re.MULTILINE)
        key = version_match.group(1) if version_match else (
            accession_match.group(1) if accession_match else ""
        )
        if not key:
            continue

        definition_parts: list[str] = []
        in_definition = False
        for line in block.splitlines():
            if line.startswith("DEFINITION"):
                in_definition = True
                definition_parts.append(line[len("DEFINITION"):].strip())
            elif in_definition and line.startswith("            "):
                definition_parts.append(line.strip())
            elif in_definition:
                break
        organism_match = re.search(r"^\s+ORGANISM\s+(.+)$", block, re.MULTILINE)
        origin_match = re.search(r"^ORIGIN\s*\n(.*)$", block, re.MULTILINE | re.DOTALL)
        sequence = ""
        if origin_match:
            sequence = re.sub(r"[^A-Za-z]", "", origin_match.group(1)).upper()
        parsed[key] = {
            "ncbi_accession_record": accession_match.group(1) if accession_match else "",
            "ncbi_version_record": version_match.group(1) if version_match else "",
            "ncbi_definition": " ".join(definition_parts),
            "ncbi_organism": organism_match.group(1).strip() if organism_match else "",
            "ncbi_ec_numbers": ";".join(sorted(set(re.findall(r'/EC_number="([0-9.]+)"', block)))),
            "ncbi_uniprot_xrefs": ";".join(sorted(set(
                re.findall(r'/db_xref="UniProtKB/(?:TrEMBL|Swiss-Prot):([A-Z0-9]+)"', block)
            ))),
            "ncbi_sequence_length_aa": str(len(sequence)),
            "ncbi_sequence_sha256": hashlib.sha256(sequence.encode()).hexdigest().upper() if sequence else "",
            "ncbi_sequence_aa": sequence,
            "ncbi_record_present": "true",
        }
    return parsed


def main() -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    with POOL.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            grouped[row["protein_accession_species"]].append(row)
    if len(grouped) != 96:
        raise RuntimeError(f"Expected 96 distinct core-pool proteins, got {len(grouped)}")

    accession_to_labels: dict[str, list[str]] = defaultdict(list)
    for label in grouped:
        accession = accession_from_label(label)
        if accession:
            accession_to_labels[accession].append(label)

    retrieved: dict[str, dict[str, str]] = {}
    accessions = sorted(accession_to_labels)
    for start in range(0, len(accessions), CHUNK_SIZE):
        chunk = accessions[start:start + CHUNK_SIZE]
        records = parse_records(fetch_genbank(chunk))
        retrieved.update(records)
        print(f"NCBI batch {start // CHUNK_SIZE + 1}: requested={len(chunk)} returned={len(records)}")
        time.sleep(0.45)

    for start in range(0, len(accessions), CHUNK_SIZE):
        chunk = accessions[start:start + CHUNK_SIZE]
        fasta_sequences = parse_fasta(fetch_fasta(chunk))
        for accession, sequence in fasta_sequences.items():
            if accession in retrieved:
                retrieved[accession]["ncbi_sequence_aa"] = sequence
                retrieved[accession]["ncbi_sequence_length_aa"] = str(len(sequence))
                retrieved[accession]["ncbi_sequence_sha256"] = hashlib.sha256(
                    sequence.encode()
                ).hexdigest().upper()
        print(f"NCBI FASTA batch {start // CHUNK_SIZE + 1}: requested={len(chunk)} returned={len(fasta_sequences)}")
        time.sleep(0.45)

    output_rows = []
    fasta_records: list[str] = []
    for label, source_rows in sorted(grouped.items()):
        accession = accession_from_label(label)
        substrates = Counter(row["substrate"] for row in source_rows)
        record = retrieved.get(accession, {}) if accession else {}
        status = "200" if record else ("unresolved_accession_query" if accession else "no_accession_in_source_label")
        output_rows.append(
            {
                "source_protein_id": label,
                "ncbi_accession": accession,
                "core_pool_below_background_cells": len(source_rows),
                "core_pool_substrate_counts": "; ".join(
                    f"{name}:{substrates[name]}" for name in sorted(substrates)
                ),
                "ncbi_fetch_status": status,
                **record,
                "interpretation": (
                    "GenBank protein metadata; not BRENDA assay coverage"
                    if record else "No accession-level NCBI/BRENDA query; preserve as unresolved source label"
                ),
            }
        )
        if record.get("ncbi_sequence_aa"):
            fasta_records.append(
                f">{accession} source_id={label}\n"
                + "\n".join(record["ncbi_sequence_aa"][i:i + 70]
                           for i in range(0, len(record["ncbi_sequence_aa"]), 70))
            )

    fields = [field for field in output_rows[0] if field != "ncbi_sequence_aa"]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: value for key, value in row.items() if key != "ncbi_sequence_aa"}
                         for row in output_rows)
    fasta_path = HERE / "gh1_nims_core96_ncbi_sequences.fasta"
    fasta_path.write_text("\n".join(fasta_records) + "\n", encoding="ascii")

    ec_counts = Counter(
        ec for row in output_rows for ec in row.get("ncbi_ec_numbers", "").split(";") if ec
    )
    print(f"core_pool_proteins={len(output_rows)}")
    print(f"versioned_accessions={len(accessions)}")
    print(f"non_accessioned_source_labels={len(grouped) - len(accessions)}")
    print(f"ncbi_records_returned={sum(row['ncbi_fetch_status'] == '200' for row in output_rows)}")
    print(f"unique_explicit_ec_numbers={sorted(ec_counts)}")
    print(f"output={OUTPUT}")
    print(f"sequence_fasta={fasta_path}; sequences={len(fasta_records)}")


if __name__ == "__main__":
    main()
