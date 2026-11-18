"""Strict, auditable pipeline for narrative biochemical negative evidence."""

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).parent
SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|(?<=[。！？])")
FIGURE_REF_RE = re.compile(
    r"\b(?:fig(?:ure)?s?|tables?|supplement(?:ary)?|supporting information|extended data|SI)\b|"
    r"图\s*\d|表\s*\d|补充(?:材料|信息)", re.I,
)
EXCLUDED_SECTION_RE = re.compile(
    r"references?|bibliograph|acknowledg|author response|peer review|reviewer|"
    r"competing interests?|funding|data availability|code availability|参考文献|致谢|审稿",
    re.I,
)
UI_NOISE_RE = re.compile(
    r"unable to load your collection|please try again|open in a new tab|download pdf|"
    r"copyright notice|skip to main content", re.I,
)
NEGATIVE_CUE_PATTERNS = {
    "not_observed": re.compile(r"\b(?:no|not)\s+(?:product|activity|signal|formation|conversion)\b|not observed|not detected|undetectable", re.I),
    "inactive": re.compile(r"\binactiv(?:e|ated|ity)|loss of function|abolish(?:ed|ment)?\b", re.I),
    "low_performance": re.compile(r"\blow(?:er)?\s+(?:activity|yield|conversion|selectivity|enantioselectivity|reactivity|rate)|trace (?:activity|yield|product)|poor(?:ly)? (?:active|reactive|tolerated)", re.I),
    "relative_decrease": re.compile(r"\breduc(?:ed|tion)|decreas(?:ed|e)|lower than|less than|impaired|detrimental|did not improve|no improvement", re.I),
    "failure": re.compile(r"\bfailed?\b|\bunsuccessful\b|unable to|could not|did not|thwarted", re.I),
    "conditional": re.compile(r"\bprecipitat|destabili[sz]|deactivat|aggregation|oxygen sensitivity|intolerance", re.I),
    "chinese": re.compile(r"未检测到|未观察到|无活性|失活|低活性|低产率|低转化|降低|下降|失败|不能|无法|痕量"),
}
EXCLUSION_PATTERNS = {
    "computational_only": re.compile(r"\bDFT\b|in silico|transition state|did not converge|QM/MM|spin-state", re.I),
    "purification_or_instrument": re.compile(r"\bFPLC\b|chromatography system|over-pressur|could not be purified", re.I),
    "crystallography_interpretation": re.compile(r"electron density|could not be (?:unambiguously )?modelled|could not be (?:unambiguously )?modeled", re.I),
    "non_enzyme_control": re.compile(r"enzyme[- ]free|uncataly[sz]ed|absence of (?:the )?enzyme|no-enzyme control", re.I),
    "literature_background": re.compile(r"previous studies|previously reported|has been shown|for example.*mutation", re.I),
}
ALLOWED_INCREMENTAL_STATUS = {
    "narrative_increment", "figure_table_linked", "figure_table_duplicate",
    "database_duplicate", "unknown",
}
ALLOWED_REVIEW_DECISIONS = {"accepted", "rejected"}


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


def tag_name(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def element_text(element):
    return " ".join("".join(element.itertext()).split())


def nearest_section(element, parents):
    current = element
    while current in parents:
        current = parents[current]
        if tag_name(current) == "sec":
            for child in current:
                if tag_name(child) == "title":
                    return element_text(child)
    return ""


def text_from_xml(path):
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return text_from_html(Path(path).read_text(encoding="utf-8", errors="replace"))
    parents = {child: parent for parent in root.iter() for child in parent}
    blocks = []
    for element in root.iter():
        tag = tag_name(element)
        if tag not in {"p", "caption"}:
            continue
        value = element_text(element)
        if value:
            blocks.append({
                "text": value,
                "kind": "caption" if tag == "caption" else "body_paragraph",
                "section": nearest_section(element, parents),
            })
    return blocks


class NarrativeHTMLParser(HTMLParser):
    TARGETS = {"p": "body_paragraph", "figcaption": "caption", "h1": "heading", "h2": "heading", "h3": "heading", "h4": "heading"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.capture_tag = None
        self.capture_kind = None
        self.depth = 0
        self.buffer = []
        self.section = ""
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self.capture_tag is not None:
            self.depth += 1
        elif tag in self.TARGETS:
            self.capture_tag = tag
            self.capture_kind = self.TARGETS[tag]
            self.depth = 0
            self.buffer = []

    def handle_data(self, data):
        if self.capture_tag is not None:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if self.capture_tag is None:
            return
        if self.depth:
            self.depth -= 1
            return
        if tag.lower() != self.capture_tag:
            return
        value = " ".join(" ".join(self.buffer).split())
        if value:
            if self.capture_kind == "heading":
                self.section = value
            else:
                self.blocks.append({"text": value, "kind": self.capture_kind, "section": self.section})
        self.capture_tag = None
        self.capture_kind = None
        self.buffer = []


def text_from_html(raw):
    parser = NarrativeHTMLParser()
    parser.feed(raw)
    return parser.blocks


def text_blocks(path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in {".xml", ".jats", ".nxml"}:
        return text_from_xml(path)
    raw = path.read_text(encoding="utf-8", errors="replace")
    if suffix in {".html", ".htm"}:
        return text_from_html(raw)
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    return [{"text": x.strip(), "kind": "body_paragraph", "section": ""}
            for x in re.split(r"\n\s*\n+", raw) if x.strip()]


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


def source_flags(text, section, kind):
    flags = []
    if UI_NOISE_RE.search(text):
        flags.append("ui_noise")
    if EXCLUDED_SECTION_RE.search(section or ""):
        flags.append("excluded_section")
    if kind == "caption":
        flags.append("caption_source")
    return flags


def parse_document(item):
    path = Path(item["path"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    units = []
    for index, block in enumerate(text_blocks(path)):
        text = block["text"]
        flags = source_flags(text, block["section"], block["kind"])
        if "ui_noise" in flags:
            continue
        uid = stable_id("U_", item["paper_id"], index, text)
        sentences = []
        for start, end, sentence_text in split_sentences(text):
            sentences.append({
                "sentence_id": stable_id("S_", item["paper_id"], uid, start, end, sentence_text),
                "unit_id": uid, "char_start": start, "char_end": end, "text": sentence_text,
                "kind": block["kind"], "section": block["section"], "source_flags": flags,
            })
        units.append({
            "unit_id": uid, "kind": block["kind"], "section": block["section"],
            "source_flags": flags, "text": text, "sentences": sentences,
        })
    return {
        "paper_id": item["paper_id"], "doi": item.get("doi"), "title": item.get("title"),
        "url": item.get("url"), "source_path": str(path), "source_sha256": sha(path), "units": units,
    }


def build_jobs(document, max_chars=8000, max_units=3):
    jobs, current, used = [], [], 0

    def flush():
        nonlocal current, used
        if not current:
            return
        sentences = [s for unit in current for s in unit["sentences"]]
        jid = stable_id("J_", document["paper_id"], document["source_sha256"], [u["unit_id"] for u in current])
        jobs.append({
            "job_id": jid, "paper_id": document["paper_id"], "doi": document.get("doi"),
            "title": document.get("title"), "source_path": document["source_path"],
            "source_sha256": document["source_sha256"], "primary_units": current, "sentences": sentences,
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
    adapter.setdefault("training_required_fields", adapter["required_fields"])
    adapter.setdefault("allowed_record_kinds", [
        "biochemical_observation", "process_failure", "assay_failure",
        "computational_failure", "literature_background",
    ])
    adapter.setdefault("training_record_kinds", ["biochemical_observation"])
    adapter.setdefault("numeric_preferred_outcomes", [
        "low_activity", "low_yield", "low_selectivity", "relative_weakening",
    ])
    if not set(adapter["training_required_fields"]).issubset(fields):
        raise ValueError("Adapter training_required_fields must be a subset of fields")
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
    job_ids, paper_rows = [], []
    for item in manifest:
        document = parse_document(item)
        write_json(out / "documents" / f"{item['paper_id']}.json", document)
        jobs = build_jobs(document, args.max_chars, args.max_units)
        for job in jobs:
            write_json(out / "jobs" / f"{job['job_id']}.json", job)
            job_ids.append(job["job_id"])
        paper_rows.append({
            "paper_id": item["paper_id"], "doi": item.get("doi"), "title": item.get("title"),
            "source_sha256": document["source_sha256"], "jobs": len(jobs), "body_units": len(document["units"]),
        })
    write_json(out / "manifest.json", {
        "pipeline": "strict_narrative_negative_evidence_v2", "adapter_id": adapter["adapter_id"],
        "papers": paper_rows, "job_ids": job_ids, "jobs": len(job_ids), "api_requests_sent": 0,
        "note": "prepare parses sources only; it does not perform semantic extraction",
    })
    print(json.dumps({"papers": len(paper_rows), "jobs": len(job_ids), "api_requests_sent": 0,
                      "semantic_records": 0}, ensure_ascii=False, indent=2))


def cue_hits(text):
    return [name for name, pattern in NEGATIVE_CUE_PATTERNS.items() if pattern.search(text)]


def exclusion_hits(text):
    return [name for name, pattern in EXCLUSION_PATTERNS.items() if pattern.search(text)]


def scan(args):
    workspace = Path(args.workspace)
    manifest = read_json(workspace / "manifest.json")
    totals = {"papers": len(manifest["papers"]), "sentences": 0, "raw_candidates": 0,
              "eligible_for_review": 0, "excluded_candidates": 0}
    per_paper = []
    for paper in manifest["papers"]:
        document = read_json(workspace / "documents" / f"{paper['paper_id']}.json")
        candidates = []
        for unit in document["units"]:
            sentences = unit["sentences"]
            totals["sentences"] += len(sentences)
            for index, sentence in enumerate(sentences):
                cues = cue_hits(sentence["text"])
                if not cues:
                    continue
                exclusions = exclusion_hits(sentence["text"])
                exclusions.extend(x for x in sentence["source_flags"] if x in {"excluded_section", "ui_noise"})
                if FIGURE_REF_RE.search(sentence["text"]):
                    exclusions.append("figure_table_reference_requires_resolution")
                context = sentences[max(0, index - 1): min(len(sentences), index + 2)]
                candidates.append({
                    "candidate_id": stable_id("C_", paper["paper_id"], sentence["sentence_id"]),
                    "paper_id": paper["paper_id"], "sentence_id": sentence["sentence_id"],
                    "text": sentence["text"], "section": sentence["section"], "kind": sentence["kind"],
                    "cue_hits": cues, "exclusion_flags": sorted(set(exclusions)),
                    "review_status": "excluded_by_rule" if exclusions else "eligible_for_review",
                    "context": [{"sentence_id": x["sentence_id"], "text": x["text"]} for x in context],
                })
        raw = len(candidates)
        eligible = sum(c["review_status"] == "eligible_for_review" for c in candidates)
        totals["raw_candidates"] += raw
        totals["eligible_for_review"] += eligible
        totals["excluded_candidates"] += raw - eligible
        per_paper.append({"paper_id": paper["paper_id"], "raw_candidates": raw,
                          "eligible_for_review": eligible, "excluded_candidates": raw - eligible})
        write_json(workspace / "candidates" / f"{paper['paper_id']}.json", {
            "pipeline": manifest["pipeline"], "paper_id": paper["paper_id"], "candidates": candidates,
        })
    totals["per_paper"] = per_paper
    write_json(workspace / "candidate_summary.json", totals)
    print(json.dumps(totals, ensure_ascii=False, indent=2))


def job_path(workspace, job_id):
    path = Path(workspace) / "jobs" / f"{job_id}.json"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def render_prompt(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    job = read_json(job_path(workspace, args.job_id))
    template_name = "discovery_generic.md" if args.stage == "discovery" else "extraction_generic.md"
    template = (ROOT / "prompts" / template_name).read_text(encoding="utf-8")
    candidate_file = workspace / "candidates" / f"{job['paper_id']}.json"
    candidates = []
    if candidate_file.is_file():
        job_sentence_ids = {s["sentence_id"] for s in job["sentences"]}
        candidates = [c for c in read_json(candidate_file)["candidates"] if c["sentence_id"] in job_sentence_ids]
    text = template + "\n\n## ADAPTER\n" + json.dumps(adapter, ensure_ascii=False, indent=2)
    text += "\n\n## RULE-BASED CANDIDATES\n" + json.dumps(candidates, ensure_ascii=False, indent=2)
    text += "\n\n## JOB\n" + json.dumps(job, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        print(text)


def sentence_map(job):
    return {s["sentence_id"]: s for s in job["sentences"]}


def training_gate_reasons(record, job, adapter):
    reasons = []
    if record["outcome_type"] not in adapter["negative_outcomes"]:
        reasons.append("outcome_not_training_negative")
    if record["record_kind"] not in adapter["training_record_kinds"]:
        reasons.append("record_kind_not_biochemical_training_target")
    if record["incremental_status"] != "narrative_increment":
        reasons.append("not_verified_narrative_increment")
    if record.get("semantic_review") != "accepted":
        reasons.append("human_review_required")
    values, evidence = record["values"], record["evidence"]
    for field in adapter["training_required_fields"]:
        if values.get(field) is None or not evidence.get(field):
            reasons.append(f"training_field_missing:{field}")
    if record["outcome_type"] in adapter["numeric_preferred_outcomes"]:
        if not values.get("result_value") and "explicit_qualitative_result" not in record["qualifiers"]:
            reasons.append("result_value_or_explicit_qualitative_required")
    smap = sentence_map(job)
    evidence_ids = {item["sentence_id"] for items in evidence.values() if isinstance(items, list)
                    for item in items if isinstance(item, dict) and item.get("sentence_id") in smap}
    for sid in evidence_ids:
        sentence = smap[sid]
        if "excluded_section" in sentence.get("source_flags", []):
            reasons.append("evidence_from_excluded_section")
        if sentence.get("kind") == "caption":
            reasons.append("caption_requires_figure_resolution")
        if FIGURE_REF_RE.search(sentence["text"]):
            reasons.append("figure_table_reference_requires_resolution")
        for hit in exclusion_hits(sentence["text"]):
            reasons.append(f"excluded_semantic_scope:{hit}")
    return sorted(set(reasons))


def validate_record(record, job, adapter, index):
    errors = []
    expected_keys = {"record_id", "outcome_type", "record_kind", "incremental_status", "values", "evidence", "qualifiers"}
    fields = set(adapter["fields"])
    if not isinstance(record, dict):
        return {"index": index, "record": record, "errors": ["record_not_object"]}
    if set(record) != expected_keys:
        errors.append("record_keys_invalid")
    if not isinstance(record.get("record_id"), str) or not record.get("record_id"):
        errors.append("record_id_invalid")
    if record.get("outcome_type") not in adapter["outcome_types"]:
        errors.append("outcome_type_invalid")
    if record.get("record_kind") not in adapter["allowed_record_kinds"]:
        errors.append("record_kind_invalid")
    if record.get("incremental_status") not in ALLOWED_INCREMENTAL_STATUS:
        errors.append("incremental_status_invalid")
    values = record.get("values")
    if not isinstance(values, dict) or set(values) != fields:
        errors.append("values_keys_invalid")
        values = values if isinstance(values, dict) else {}
    evidence = record.get("evidence")
    if not isinstance(evidence, dict) or set(evidence) != fields:
        errors.append("evidence_keys_invalid")
        evidence = evidence if isinstance(evidence, dict) else {}
    qualifiers = record.get("qualifiers")
    if not isinstance(qualifiers, list) or any(not isinstance(x, str) for x in qualifiers):
        errors.append("qualifiers_invalid")
        qualifiers = []
    smap = sentence_map(job)
    for field in fields:
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
    if errors:
        return {"index": index, "record": record, "errors": sorted(set(errors))}
    canonical = {"outcome_type": record["outcome_type"], "record_kind": record["record_kind"], "values": values}
    key = hashlib.sha256(json.dumps(canonical, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    checked = {
        "record_key": f"{job['paper_id']}:{key[:20]}", "record_id": record["record_id"],
        "paper_id": job["paper_id"], "job_id": job["job_id"], "doi": job.get("doi"),
        "source_path": job["source_path"], "source_sha256": job["source_sha256"],
        "outcome_type": record["outcome_type"], "record_kind": record["record_kind"],
        "incremental_status": record["incremental_status"], "values": values, "evidence": evidence,
        "qualifiers": qualifiers, "semantic_review": "pending", "review": None,
        "ready_for_training": False,
    }
    checked["training_gate_reasons"] = training_gate_reasons(checked, job, adapter)
    return checked


def validate_response(response, job, adapter):
    if not isinstance(response, dict):
        raise ValueError("Response must be an object")
    if response.get("schema_version") != 2:
        raise ValueError("schema_version must be 2; v1 records cannot be training-ready")
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
        (rejected if "errors" in checked else accepted).append(checked)
    unresolved = [] if status == "observations" else [{
        "job_id": job["job_id"], "paper_id": job["paper_id"], "status": status,
        "reason": response.get("reason"),
    }]
    return {
        "pipeline": "strict_narrative_negative_evidence_v2", "adapter_id": adapter["adapter_id"],
        "job_id": job["job_id"], "paper_id": job["paper_id"], "accepted": accepted,
        "rejected": rejected, "unresolved": unresolved,
        "coverage_notes": response.get("coverage_notes", []),
        "semantic_validation": "pending_human_adjudication",
    }


def validate(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    manifest = read_json(workspace / "manifest.json")
    totals = {"jobs": len(manifest["job_ids"]), "processed": 0, "structurally_valid": 0,
              "rejected": 0, "unresolved": 0, "training_ready": 0}
    for jid in manifest["job_ids"]:
        response_path = workspace / "responses" / f"{jid}.json"
        if not response_path.is_file():
            continue
        job = read_json(job_path(workspace, jid))
        result = validate_response(read_json(response_path), job, adapter)
        write_json(workspace / "results" / f"{jid}.json", result)
        totals["processed"] += 1
        totals["structurally_valid"] += len(result["accepted"])
        totals["rejected"] += len(result["rejected"])
        totals["unresolved"] += len(result["unresolved"])
    write_json(workspace / "validation_summary.json", totals)
    print(json.dumps(totals, ensure_ascii=False, indent=2))


def adjudicate(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    decisions = read_json(args.decisions)
    if not isinstance(decisions, list):
        raise ValueError("Decisions must be a JSON array")
    by_key = {}
    required = {"record_key", "decision", "reviewer", "reviewed_at", "record_kind", "incremental_status", "notes"}
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) != required:
            raise ValueError("Each decision must contain exactly: " + ", ".join(sorted(required)))
        if decision["decision"] not in ALLOWED_REVIEW_DECISIONS:
            raise ValueError("decision must be accepted or rejected")
        if decision["record_kind"] not in adapter["allowed_record_kinds"]:
            raise ValueError("review record_kind invalid")
        if decision["incremental_status"] not in ALLOWED_INCREMENTAL_STATUS:
            raise ValueError("review incremental_status invalid")
        if not decision["reviewer"] or not decision["reviewed_at"]:
            raise ValueError("reviewer and reviewed_at are required")
        if decision["record_key"] in by_key:
            raise ValueError(f"Duplicate decision for {decision['record_key']}")
        by_key[decision["record_key"]] = decision
    found = set()
    totals = {"records": 0, "reviewed": 0, "accepted": 0, "rejected": 0, "training_ready": 0}
    for result_path in (workspace / "results").glob("*.json"):
        result = read_json(result_path)
        job = read_json(job_path(workspace, result["job_id"]))
        for record in result["accepted"]:
            totals["records"] += 1
            decision = by_key.get(record["record_key"])
            if decision:
                found.add(record["record_key"])
                totals["reviewed"] += 1
                totals[decision["decision"]] += 1
                record["record_kind"] = decision["record_kind"]
                record["incremental_status"] = decision["incremental_status"]
                record["semantic_review"] = decision["decision"]
                record["review"] = decision
            record["training_gate_reasons"] = training_gate_reasons(record, job, adapter)
            if record["semantic_review"] == "rejected":
                record["training_gate_reasons"] = sorted(set(record["training_gate_reasons"] + ["human_rejected"]))
            record["ready_for_training"] = not record["training_gate_reasons"]
            totals["training_ready"] += int(record["ready_for_training"])
        result["semantic_validation"] = "human_adjudication_applied"
        write_json(workspace / "adjudicated" / result_path.name, result)
    unknown = set(by_key) - found
    if unknown:
        raise ValueError("Decisions reference unknown record keys: " + ", ".join(sorted(unknown)))
    write_json(workspace / "adjudication_summary.json", totals)
    print(json.dumps(totals, ensure_ascii=False, indent=2))


def iter_final_results(workspace, manifest):
    for jid in manifest["job_ids"]:
        adjudicated = workspace / "adjudicated" / f"{jid}.json"
        validated = workspace / "results" / f"{jid}.json"
        path = adjudicated if adjudicated.is_file() else validated
        if path.is_file():
            yield read_json(path)


def export(args):
    workspace = Path(args.workspace)
    adapter = load_adapter(workspace / "adapter.json")
    manifest = read_json(workspace / "manifest.json")
    values, rejected, unresolved = [], [], []
    for result in iter_final_results(workspace, manifest):
        values.extend(result["accepted"])
        rejected.extend(result["rejected"])
        unresolved.extend(result["unresolved"])
    out = workspace / "exports"
    out.mkdir(exist_ok=True)
    write_json(out / "records.json", values)
    write_json(out / "training_ready_records.json", [x for x in values if x["ready_for_training"]])
    write_json(out / "rejected.json", rejected)
    write_json(out / "unresolved.json", unresolved)
    columns = ["record_key", "paper_id", "job_id", "doi", "outcome_type", "record_kind",
               "incremental_status"] + adapter["fields"] + ["evidence", "qualifiers", "semantic_review",
               "training_gate_reasons", "ready_for_training"]
    with (out / "records.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in values:
            flat = dict(row)
            flat.update(row["values"])
            flat["evidence"] = json.dumps(row["evidence"], ensure_ascii=False)
            flat["qualifiers"] = json.dumps(row["qualifiers"], ensure_ascii=False)
            flat["training_gate_reasons"] = json.dumps(row["training_gate_reasons"], ensure_ascii=False)
            writer.writerow(flat)
    summary = {
        "pipeline": "strict_narrative_negative_evidence_v2", "adapter_id": adapter["adapter_id"],
        "papers": len(manifest["papers"]), "jobs": len(manifest["job_ids"]),
        "structurally_valid_records": len(values),
        "human_reviewed_records": sum(x["semantic_review"] in ALLOWED_REVIEW_DECISIONS for x in values),
        "human_rejected_records": sum(x["semantic_review"] == "rejected" for x in values),
        "training_ready_records": sum(x["ready_for_training"] for x in values),
        "unresolved_jobs": len(unresolved),
        "claim_boundary": "Only training_ready_records are verified narrative increments suitable as candidate model inputs.",
    }
    write_json(out / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def status(args):
    workspace = Path(args.workspace)
    manifest = read_json(workspace / "manifest.json")
    response_ids = {p.stem for p in (workspace / "responses").glob("*.json")} if (workspace / "responses").exists() else set()
    result_ids = {p.stem for p in (workspace / "results").glob("*.json")} if (workspace / "results").exists() else set()
    adjudicated_ids = {p.stem for p in (workspace / "adjudicated").glob("*.json")} if (workspace / "adjudicated").exists() else set()
    candidate_summary = read_json(workspace / "candidate_summary.json") if (workspace / "candidate_summary.json").is_file() else None
    print(json.dumps({
        "pipeline": manifest["pipeline"], "adapter_id": manifest["adapter_id"],
        "papers": len(manifest["papers"]), "jobs": len(manifest["job_ids"]),
        "candidate_scan": candidate_summary, "responses": len(response_ids),
        "validated_results": len(result_ids), "adjudicated_results": len(adjudicated_ids),
        "pending_response_jobs": len(set(manifest["job_ids"]) - response_ids),
        "pending_validation_jobs": len(response_ids - result_ids),
        "pending_adjudication_jobs": len(result_ids - adjudicated_ids),
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
    p = sub.add_parser("scan")
    p.add_argument("--workspace", required=True, type=Path)
    p = sub.add_parser("prompt")
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--job-id", required=True)
    p.add_argument("--stage", required=True, choices=["discovery", "extraction"])
    p.add_argument("--out", type=Path)
    p = sub.add_parser("adjudicate")
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--decisions", required=True, type=Path)
    for name in ("validate", "export", "status"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args)
    elif args.command == "scan":
        scan(args)
    elif args.command == "prompt":
        render_prompt(args)
    elif args.command == "validate":
        validate(args)
    elif args.command == "adjudicate":
        adjudicate(args)
    elif args.command == "export":
        export(args)
    else:
        status(args)


if __name__ == "__main__":
    main()
