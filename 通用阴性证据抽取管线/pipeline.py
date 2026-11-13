"""Domain-adapter based, offline-first literature negative-evidence pipeline."""

import argparse
import csv
import hashlib
import html
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).parent
SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|(?<=[。！？])")
NEGATIVE_CUES = re.compile(
    r"\b(?:not tested|not reported|unknown|failed|failure|inactive|no detectable|"
    r"low activity|low yield|low conversion|no conversion|loss of function|"
    r"reduced|decreased|did not|unable to|could not)\b|未测试|未报道|未知|失败|"
    r"失活|低活性|低产率|低转化|未检测到|不能|无法|降低|下降",
    re.I,
)


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def stable_id(prefix, *parts):
    raw = json.dumps(parts, ensure_ascii=False, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def normalize(text):
    return re.sub(r"\s+", " ", text).strip().casefold()


def text_from_xml(path):
    root = ET.parse(path).getroot()
    blocks = []
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1].lower()
        if tag not in {"p", "paragraph", "caption", "title", "abstract"}:
            continue
        value = " ".join("".join(element.itertext()).split())
        if value:
            blocks.append(value)
    return blocks


def text_blocks(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".xml", ".jats", ".nxml"}:
        return text_from_xml(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        raw = re.sub(r"<[^>]+>", " ", raw)
        raw = html.unescape(raw)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    return [x.strip() for x in re.split(r"\n\s*\n+", raw) if x.strip()]


def split_sentences(text):
    values = []
    start = 0
    for match in SENTENCE_RE.finditer(text):
        end = match.start() if match.group(0).isspace() else match.end()
        part = text[start:end].strip()
        if part:
            left = text.find(part, start, end + 1)
            values.append((left, left + len(part), part))
        start = match.end()
    part = text[start:].strip()
    if part:
        left = text.find(part, start)
        values.append((left, left + len(part), part))
    return values


def parse_document(item):
    path = Path(item["path"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    blocks = text_blocks(path)
    units = []
    for index, block in enumerate(blocks):
        uid = stable_id("U_", item["paper_id"], index, block)
        sentences = []
        for start, end, text in split_sentences(block):
            sentences.append({
                "sentence_id": stable_id("S_", item["paper_id"], uid, start, end, text),
                "unit_id": uid,
                "char_start": start,
                "char_end": end,
                "text": text,
            })
        units.append({"unit_id": uid, "kind": "body_paragraph", "text": block, "sentences": sentences})
    return {
        "paper_id": item["paper_id"],
        "doi": item.get("doi"),
        "title": item.get("title"),
        "url": item.get("url"),
        "source_path": str(path),
        "source_sha256": sha(path),
        "units": units,
    }


def build_jobs(document, max_chars=8000, max_units=3):
    jobs = []
    current = []
    used = 0

    def flush():
        nonlocal current, used
        if not current:
            return
        sentences = [s for unit in current for s in unit["sentences"]]
        jid = stable_id("J_", document["paper_id"], document["source_sha256"], [u["unit_id"] for u in current])
        jobs.append({
            "job_id": jid,
            "paper_id": document["paper_id"],
            "doi": document.get("doi"),
            "title": document.get("title"),
            "source_path": document["source_path"],
            "source_sha256": document["source_sha256"],
            "primary_units": current,
            "sentences": sentences,
        })
        current, used = [], 0

    for unit in document["units"]:
        length = len(unit["text"])
        if current and (used + length > max_chars or len(current) >= max_units):
            flush()
        current.append(unit)
        used += length
    flush()
    return jobs


def load_adapter(path):
    adapter = read_json(path)
    required = {"adapter_id", "fields", "required_fields", "outcome_types", "negative_outcomes", "non_negative_outcomes"}
    missing = required - set(adapter)
    if missing:
        raise ValueError("Adapter missing keys: " + ", ".join(sorted(missing)))
    fields = adapter["fields"]
    if not fields or len(fields) != len(set(fields)):
        raise ValueError("Adapter fields must be a nonempty unique list")
    if not set(adapter["required_fields"]).issubset(fields):
        raise ValueError("Adapter required_fields must be a subset of fields")
    if not set(adapter["negative_outcomes"]).issubset(adapter["outcome_types"]):
        raise ValueError("Adapter negative_outcomes must be allowed outcomes")
    return adapter


def prepare(args):
    out = Path(args.out)
    if out.exists():
        raise ValueError(f"Workspace exists; choose a new path or use the existing workspace: {out}")
    manifest = read_json(args.manifest)
    if not isinstance(manifest, list) or not manifest:
        raise ValueError("Manifest must be a nonempty JSON array")
    adapter = load_adapter(args.adapter)
    paper_ids = [item.get("paper_id") for item in manifest]
    if any(not isinstance(x, str) or not x for x in paper_ids) or len(set(paper_ids)) != len(paper_ids):
        raise ValueError("Manifest paper_id values must be unique nonempty strings")
    out.mkdir(parents=True)
    write_json(out / "adapter.json", adapter)
    write_json(out / "input_manifest.json", manifest)
    job_ids = []
    paper_rows = []
    for item in manifest:
        document = parse_document(item)
        write_json(out / "documents" / f"{item['paper_id']}.json", document)
        jobs = build_jobs(document, args.max_chars, args.max_units)
        for job in jobs:
            write_json(out / "jobs" / f"{job['job_id']}.json", job)
            job_ids.append(job["job_id"])
        paper_rows.append({
            "paper_id": item["paper_id"], "doi": item.get("doi"),
            "title": item.get("title"), "source_sha256": document["source_sha256"],
            "jobs": len(jobs), "body_units": len(document["units"]),
        })
    write_json(out / "manifest.json", {
        "pipeline": "generic_negative_evidence_v1",
        "adapter_id": adapter["adapter_id"],
        "papers": paper_rows,
        "job_ids": job_ids,
        "jobs": len(job_ids),
        "api_requests_sent": 0,
    })
    print(json.dumps({"papers": len(paper_rows), "jobs": len(job_ids), "api_requests_sent": 0}, ensure_ascii=False, indent=2))


def job_path(workspace, job_id):
    path = Path(workspace) / "jobs" / f"{job_id}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def render_prompt(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    job = read_json(job_path(workspace, args.job_id))
    if args.stage == "discovery":
        template = (ROOT / "prompts" / "discovery_generic.md").read_text(encoding="utf-8")
    else:
        template = (ROOT / "prompts" / "extraction_generic.md").read_text(encoding="utf-8")
    payload = {
        "adapter": adapter,
        "job": job,
        "instructions": template,
    }
    text = template + "\n\n## ADAPTER\n" + json.dumps(adapter, ensure_ascii=False, indent=2)
    text += "\n\n## JOB\n" + json.dumps(payload["job"], ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)


def sentence_map(job):
    return {s["sentence_id"]: s for s in job["sentences"]}


def validate_record(record, job, adapter, index):
    errors = []
    expected_values = set(adapter["fields"])
    if not isinstance(record, dict):
        return {"index": index, "record": record, "errors": ["record_not_object"]}
    if set(record) != {"record_id", "outcome_type", "values", "evidence", "qualifiers"}:
        errors.append("record_keys_invalid")
    if not isinstance(record.get("record_id"), str) or not record.get("record_id"):
        errors.append("record_id_invalid")
    outcome = record.get("outcome_type")
    if outcome not in adapter["outcome_types"]:
        errors.append("outcome_type_invalid")
    values = record.get("values")
    if not isinstance(values, dict) or set(values) != expected_values:
        errors.append("values_keys_invalid")
        values = values if isinstance(values, dict) else {}
    evidence = record.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != expected_values:
        errors.append("evidence_keys_invalid")
        evidence = evidence if isinstance(evidence, dict) else {}
    if not isinstance(record.get("qualifiers"), list) or any(not isinstance(x, str) for x in record["qualifiers"]):
        errors.append("qualifiers_invalid")
    smap = sentence_map(job)
    for field in expected_values:
        value = values.get(field)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            errors.append(f"value_invalid:{field}")
        items = evidence.get(field, [])
        if not isinstance(items, list):
            errors.append(f"evidence_invalid:{field}")
            continue
        if value is not None and not items:
            errors.append(f"ungrounded_field:{field}")
        for item in items:
            if not isinstance(item, dict) or set(item) != {"sentence_id", "quote"}:
                errors.append(f"evidence_item_invalid:{field}")
                continue
            sid, quote = item["sentence_id"], item["quote"]
            if sid not in smap:
                errors.append(f"unknown_sentence:{field}")
            elif not isinstance(quote, str) or normalize(quote) not in normalize(smap[sid]["text"]):
                errors.append(f"quote_not_in_sentence:{field}")
    for field in adapter["required_fields"]:
        if values.get(field) is None or not evidence.get(field):
            errors.append(f"required_field_missing:{field}")
    if outcome in adapter["non_negative_outcomes"]:
        # These are valid records only for audit, never training-ready negatives.
        pass
    if not values.get("observation") and "observation" in expected_values:
        errors.append("observation_missing")
    if errors:
        return {"index": index, "record": record, "errors": sorted(set(errors))}
    canonical = {"outcome_type": outcome, "values": values, "record_id": record["record_id"]}
    key = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return {
        "record_key": f"{job['paper_id']}:{key[:20]}",
        "record_id": record["record_id"],
        "paper_id": job["paper_id"],
        "job_id": job["job_id"],
        "doi": job.get("doi"),
        "source_path": job["source_path"],
        "source_sha256": job["source_sha256"],
        "outcome_type": outcome,
        "values": values,
        "evidence": evidence,
        "qualifiers": record["qualifiers"],
        "semantic_review": "pending",
        "expert_gold": False,
        "ready_for_training": outcome in adapter["negative_outcomes"],
    }


def validate_response(response, job, adapter):
    if not isinstance(response, dict):
        raise ValueError("Response must be an object")
    if response.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    if response.get("job_id") != job["job_id"] or response.get("paper_id") != job["paper_id"]:
        raise ValueError("Response job or paper identity mismatch")
    status = response.get("status")
    if status not in {"observations", "uncertain", "not_experimental_negative"}:
        raise ValueError("status invalid")
    records = response.get("records")
    if not isinstance(records, list):
        raise ValueError("records must be an array")
    accepted, rejected = [], []
    for index, record in enumerate(records):
        checked = validate_record(record, job, adapter, index)
        if "errors" in checked:
            rejected.append(checked)
        else:
            accepted.append(checked)
    unresolved = [] if status == "observations" else [{
        "job_id": job["job_id"], "paper_id": job["paper_id"],
        "status": status, "reason": response.get("reason"),
    }]
    return {
        "pipeline": "generic_negative_evidence_v1",
        "adapter_id": adapter["adapter_id"],
        "job_id": job["job_id"],
        "paper_id": job["paper_id"],
        "accepted": accepted,
        "rejected": rejected,
        "unresolved": unresolved,
        "coverage_notes": response.get("coverage_notes", []),
        "semantic_validation": "structural_and_quote_checks_only",
    }


def validate(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    manifest = read_json(workspace / "manifest.json")
    totals = {"jobs": len(manifest["job_ids"]), "processed": 0, "accepted": 0, "rejected": 0, "unresolved": 0}
    for jid in manifest["job_ids"]:
        response_path = workspace / "responses" / f"{jid}.json"
        if not response_path.is_file():
            continue
        job = read_json(job_path(workspace, jid))
        response = read_json(response_path)
        result = validate_response(response, job, adapter)
        write_json(workspace / "results" / f"{jid}.json", result)
        totals["processed"] += 1
        totals["accepted"] += len(result["accepted"])
        totals["rejected"] += len(result["rejected"])
        totals["unresolved"] += len(result["unresolved"])
    write_json(workspace / "validation_summary.json", totals)
    print(json.dumps(totals, ensure_ascii=False, indent=2))


def export(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    manifest = read_json(workspace / "manifest.json")
    values = []
    rejected = []
    unresolved = []
    for jid in manifest["job_ids"]:
        path = workspace / "results" / f"{jid}.json"
        if not path.is_file():
            continue
        result = read_json(path)
        values.extend(result["accepted"])
        rejected.extend(result["rejected"])
        unresolved.extend(result["unresolved"])
    out = workspace / "exports"
    out.mkdir(exist_ok=True)
    write_json(out / "records.json", values)
    write_json(out / "rejected.json", rejected)
    write_json(out / "unresolved.json", unresolved)
    columns = ["record_key", "paper_id", "job_id", "doi", "outcome_type"] + adapter["fields"] + ["evidence", "qualifiers", "semantic_review", "ready_for_training"]
    with (out / "records.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in values:
            flat = dict(row)
            flat.update(row["values"])
            flat["evidence"] = json.dumps(row["evidence"], ensure_ascii=False)
            flat["qualifiers"] = json.dumps(row["qualifiers"], ensure_ascii=False)
            writer.writerow(flat)
    summary = {
        "pipeline": "generic_negative_evidence_v1",
        "adapter_id": adapter["adapter_id"],
        "papers": len(manifest["papers"]),
        "jobs": len(manifest["job_ids"]),
        "processed_jobs": len(list((workspace / "results").glob("*.json"))) if (workspace / "results").exists() else 0,
        "accepted_records": len(values),
        "rejected_records": len(rejected),
        "unresolved_jobs": len(unresolved),
        "training_ready_records": sum(r["ready_for_training"] for r in values),
        "semantic_review": "pending; structural validation is not expert gold",
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def status(args):
    workspace = Path(args.workspace)
    manifest = read_json(workspace / "manifest.json")
    responses = workspace / "responses"
    results = workspace / "results"
    response_ids = {p.stem for p in responses.glob("*.json")} if responses.exists() else set()
    result_ids = {p.stem for p in results.glob("*.json")} if results.exists() else set()
    print(json.dumps({
        "pipeline": manifest["pipeline"], "adapter_id": manifest["adapter_id"],
        "papers": len(manifest["papers"]), "jobs": len(manifest["job_ids"]),
        "responses": len(response_ids), "validated_results": len(result_ids),
        "pending_response_jobs": len(set(manifest["job_ids"]) - response_ids),
        "pending_validation_jobs": len(response_ids - result_ids),
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--adapter", required=True, type=Path)
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--max-chars", type=int, default=8000)
    p.add_argument("--max-units", type=int, default=3)
    p = sub.add_parser("prompt")
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--job-id", required=True)
    p.add_argument("--stage", required=True, choices=["discovery", "extraction"])
    p.add_argument("--out", type=Path)
    for name in ("validate", "export", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "prompt":
        render_prompt(args)
    elif args.command == "validate":
        validate(args)
    elif args.command == "export":
        export(args)
    else:
        status(args)


if __name__ == "__main__":
    main()
