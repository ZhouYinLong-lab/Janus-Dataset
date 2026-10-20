"""Retrieve a fixed existing paper cohort; preserve source-linked text and candidates."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LOG = ROOT / "research" / "beta-glucosidase-screening-log.csv"
SESSION = requests.Session()
SESSION.headers["User-Agent"] = "Janus-Dataset bounded research extraction/1.0"
RULES = {
    "explicit_no_detect": r"\b(?:no|not|without|neither|unable)\b.{0,100}\b(?:activit\w*|hydrolys\w*|cataly\w*|detect\w*|react\w*|cleav\w*|substrate\w*)\b|\b(?:activit\w*|hydrolys\w*|detect\w*)\b.{0,70}\b(?:absent|undetectable|not observed|not detected)\b",
    "weak_or_inactive": r"\b(?:negligible|inactive|inactivit\w*|undetectable|non[- ]?substrate\w*|poor(?:ly)?|weak(?:ly)?|lower activit\w*|low activit\w*)\b",
    "table_marker": r"(?:\bND\b|\bN/?D\b|not determined|not tested|not detected|[<>≤≥]\s*0?\.?\d|(?:^|\|)\s*(?:0(?:\.0+)?|[-–—])\s*(?:\||$))",
}


def flatten(element: ET.Element | None) -> str:
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip() if element is not None else ""


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def get(url: str) -> requests.Response:
    last = None
    for attempt in range(2):
        try:
            response = SESSION.get(url, timeout=35)
            response.raise_for_status()
            return response
        except requests.RequestException as error:
            last = error
            if attempt == 0:
                time.sleep(1)
    raise RuntimeError(str(last))


def blocks(root: ET.Element, pmid: str) -> list[dict]:
    rows, counter = [], 0
    seen_tables = set()
    body = root.find("body")
    if body is None:
        return rows

    def emit(kind: str, location: str, text: str) -> None:
        nonlocal counter
        if text:
            counter += 1
            rows.append(dict(pmid=pmid, block_id=f"P{pmid}-B{counter:04d}",
                             kind=kind, location=location, text=text))

    def visit(parent: ET.Element, headings: list[str]) -> None:
        for child in parent:
            if child.tag == "sec":
                title = flatten(child.find("title"))
                visit(child, headings + ([title] if title else []))
            elif child.tag == "p":
                emit("paragraph", " / ".join(headings), flatten(child))
            elif child.tag == "table-wrap":
                seen_tables.add(id(child))
                label = flatten(child.find("label")) or child.get("id", "table")
                emit("table_caption", " / ".join(headings + [label]), flatten(child.find("caption")))
                table = child.find("table")
                if table is not None:
                    for number, row in enumerate(table.findall(".//tr"), 1):
                        text = " | ".join(flatten(cell) for cell in row if cell.tag in ("td", "th"))
                        emit("table_row", " / ".join(headings + [label, f"row {number}"]), text)
                emit("table_footnote", " / ".join(headings + [label]), flatten(child.find("table-wrap-foot")))
            elif child.tag == "fig":
                emit("figure_caption", " / ".join(headings + [flatten(child.find("label"))]), flatten(child.find("caption")))
            elif child.tag not in ("title", "ref-list"):
                visit(child, headings)

    visit(body, [])
    # Some publishers place complete tables inside a paragraph. The paragraph
    # text above is retained, but append explicit rows/footnotes for those tables.
    # Appending preserves every pre-existing B identifier used by the blind reader.
    for table in body.findall(".//table-wrap"):
        if id(table) not in seen_tables:
            holder = ET.Element("wrapper")
            holder.append(table)
            visit(holder, ["nested-table readback"])
    return rows


def main() -> None:
    source_dir = HERE / "sources"
    text_dir = HERE / "paper_text"
    source_dir.mkdir(exist_ok=True)
    text_dir.mkdir(exist_ok=True)
    with LOG.open(encoding="utf-8-sig", newline="") as stream:
        selected = [r for r in csv.DictReader(stream) if r["decision"] in ("include", "include_to_fulltext")]
    ids = ",".join(r["PMID"] for r in selected)
    metadata_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={ids}&retmode=xml"
    meta_file = source_dir / "fixed_cohort_pubmed.xml"
    if not meta_file.exists():
        meta_file.write_bytes(get(metadata_url).content)
    pubmed = ET.parse(meta_file).getroot()
    identities = {}
    for article in pubmed.findall("PubmedArticle"):
        pmid = flatten(article.find(".//MedlineCitation/PMID"))
        identity = {x.get("IdType"): flatten(x) for x in article.findall(".//PubmedData/ArticleIdList/ArticleId")}
        identities[pmid] = identity
    access, all_blocks, candidates, attachments = [], [], [], []
    for order, record in enumerate(selected, 1):
        pmid = record["PMID"]
        ids_record = identities.get(pmid, {})
        pmcid = ids_record.get("pmc", "")
        entry = dict(order=order, pmid=pmid, title=record["title"], doi=ids_record.get("doi", ""),
                     previous_stage=record["stage"], pmcid=pmcid, status="no_pmc_identifier",
                     source_url="", local_xml="", sha256="", block_count=0, candidate_count=0,
                     supplement_link_count=0, error="")
        if pmcid:
            url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
            path = source_dir / f"{pmid}_{pmcid}.xml"
            entry["source_url"] = url
            try:
                if not path.exists():
                    path.write_bytes(get(url).content)
                root = ET.parse(path).getroot()
                if root.find("body") is None:
                    raise ValueError("Response has no article body")
                article_blocks = blocks(root, pmid)
                for block in article_blocks:
                    hits = [name for name, pattern in RULES.items() if re.search(pattern, block["text"], re.I)]
                    if hits:
                        candidates.append(dict(candidate_id=f"C{len(candidates) + 1:04d}", **block,
                                               matched_rules=";".join(hits)))
                all_blocks.extend(article_blocks)
                seen_supplements = set()
                for element in root.findall(".//supplementary-material"):
                    for link in element.iter():
                        href = link.get("{http://www.w3.org/1999/xlink}href")
                        if href and href not in seen_supplements:
                            seen_supplements.add(href)
                            attachments.append(dict(pmid=pmid, pmcid=pmcid, href=href,
                                                    description=flatten(element), download_status="not_attempted"))
                content = "\n\n".join(f"[{b['block_id']}] {b['kind']} | {b['location']}\n{b['text']}" for b in article_blocks)
                (text_dir / f"{pmid}.txt").write_text(content + "\n", encoding="utf-8")
                entry.update(status="fulltext_xml_obtained", local_xml=str(path.relative_to(HERE)),
                             sha256=hashlib.sha256(path.read_bytes()).hexdigest(), block_count=len(article_blocks),
                             candidate_count=sum(c["pmid"] == pmid for c in candidates),
                             supplement_link_count=sum(a["pmid"] == pmid for a in attachments))
            except (RuntimeError, ET.ParseError, ValueError) as error:
                entry.update(status="fulltext_fetch_failed", error=str(error))
        access.append(entry)
        print(f"{order}/{len(selected)} PMID {pmid}: {entry['status']}; {entry['block_count']} blocks; {entry['candidate_count']} candidates", flush=True)
    write_csv(HERE / "paper_access.csv", access, list(access[0]))
    write_csv(HERE / "source_blocks.csv", all_blocks, ["pmid", "block_id", "kind", "location", "text"])
    write_csv(HERE / "rule_candidates.csv", candidates, ["candidate_id", "pmid", "block_id", "kind", "location", "text", "matched_rules"])
    write_csv(HERE / "supplement_links.csv", attachments, ["pmid", "pmcid", "href", "description", "download_status"])
    manifest = dict(date="2026-10-18", selection_log=str(LOG.relative_to(ROOT)),
                    selection_log_sha256=hashlib.sha256(LOG.read_bytes()).hexdigest(),
                    selected_pmids=[r["PMID"] for r in selected], metadata_url=metadata_url,
                    metadata_sha256=hashlib.sha256(meta_file.read_bytes()).hexdigest(), rules=RULES,
                    selected_papers=len(selected), obtained_fulltexts=sum(r["status"] == "fulltext_xml_obtained" for r in access),
                    source_blocks=len(all_blocks), rule_candidates=len(candidates),
                    note="Candidates are unvalidated; no PMC identifier is a bounded retrieval outcome, not proof of global full-text absence.")
    (HERE / "collection_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
