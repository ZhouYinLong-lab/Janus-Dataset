"""Fetch new, explicitly open-access full-text locations from OpenAlex.

This is an additive resolver for papers already recorded in a MolGlueDB
inventory. It never clears historical attempts, never retries a URL already
recorded in ``fetch_attempts``, and only stores sources marked ``is_oa`` by
OpenAlex. The inventory is updated atomically after each paper.
"""
import argparse
import hashlib
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

from corpus import read, save, sha
from source_formats import parse_document

OPENALEX = "https://api.openalex.org/works/https://doi.org/"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
TIMEOUT = 30
MIN_INTERVAL = 0.25
MAX_BYTES = 30_000_000
PMC_URL = re.compile(r"/pmc/articles/(?:PMC)?(\d+)", re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def normalize_url(value):
    value = str(value or "").strip()
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return None
    return value


class Client:
    def __init__(self):
        self.last = 0.0

    def get(self, url, accept="application/json"):
        delay = MIN_INTERVAL - (time.monotonic() - self.last)
        if delay > 0:
            time.sleep(delay)
        self.last = time.monotonic()
        request = Request(url, headers={
            "User-Agent": "Janus-Dataset/1.0 (open-access literature retrieval)",
            "Accept": accept,
        })
        with urlopen(request, timeout=TIMEOUT) as response:
            data = response.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("response exceeds 30 MB")
            return data, response.geturl(), response.headers.get("Content-Type", "")


def append_attempt(paper, url, purpose, status, **extra):
    attempt = {"url": url, "purpose": purpose, "started_utc": now(), "status": status}
    attempt.update(extra)
    paper.setdefault("fetch_attempts", []).append(attempt)
    return attempt


def historical_urls(paper):
    return {str(a.get("url")) for a in paper.get("fetch_attempts", []) if a.get("url")}


def openalex_metadata(client, paper, allow_repeat=False):
    doi = paper.get("doi")
    if not doi:
        return None
    url = OPENALEX + quote(doi, safe="")
    if url in historical_urls(paper) and not allow_repeat:
        return None
    try:
        data, final, content_type = client.get(url)
        digest = sha_bytes(data)
        append_attempt(paper, url, "openalex_search", "received",
                       final_url=final, content_type=content_type,
                       bytes=len(data), sha256=digest)
        payload = json.loads(data.decode("utf-8"))
        if (str(payload.get("doi", "")).lower().rstrip("/") !=
                ("https://doi.org/" + doi).lower().rstrip("/")):
            append_attempt(paper, url, "openalex_identity", "identity_mismatch",
                           openalex_doi=payload.get("doi"))
            return None
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        code = getattr(exc, "code", None)
        append_attempt(paper, url, "openalex_search",
                       "rate_limited" if code == 429 else "request_failed",
                       http_status=code, error=f"{type(exc).__name__}: {exc}")
        return None


def pmc_candidate(location):
    landing = location.get("landing_page_url") or ""
    match = PMC_URL.search(landing)
    if not match:
        return None
    pmcid = "PMC" + match.group(1)
    return {
        "url": f"https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode",
        "kind": "xml",
        "basis": "OpenAlex is_oa=true; PubMed Central repository",
        "origin": "openalex_pmc",
    }


def candidates(payload):
    locations = []
    best = payload.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    locations.extend(x for x in (payload.get("locations") or [])
                     if isinstance(x, dict) and x is not best)
    result, seen = [], set()
    for location in locations:
        if location.get("is_oa") is not True:
            continue
        pmc = pmc_candidate(location)
        if pmc and pmc["url"] not in seen:
            result.append(pmc)
            seen.add(pmc["url"])
        pdf = normalize_url(location.get("pdf_url"))
        if pdf and pdf not in seen:
            result.append({"url": pdf, "kind": "pdf",
                           "basis": "OpenAlex is_oa=true; OA location pdf",
                           "origin": "openalex_oa_location"})
            seen.add(pdf)
        landing = normalize_url(location.get("landing_page_url"))
        if landing and landing not in seen and "doi.org/" not in landing:
            result.append({"url": landing, "kind": "html",
                           "basis": "OpenAlex is_oa=true; OA location landing page",
                           "origin": "openalex_oa_location"})
            seen.add(landing)
    return result


def persist(folder, papers, summary):
    summary["availability_counts"] = dict(sorted(Counter(p.get("availability") for p in papers).items()))
    summary["with_local_source"] = sum(bool(p.get("path")) for p in papers)
    save(folder / "papers.json", papers)
    save(folder / "source_inventory.json", summary)


def store(folder, paper, candidate, data, final_url, content_type, openalex_id):
    kind = candidate["kind"]
    if kind == "pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("expected PDF bytes")
    if kind == "xml" and not (data.lstrip().startswith(b"<") and
                               re.search(rb"<(?:\w+:)?(?:article|collection)[\s>]", data)):
        raise ValueError("expected article XML")
    if kind == "html" and (data.startswith(b"%PDF-") or b"<" not in data):
        raise ValueError("expected HTML bytes")
    digest = sha_bytes(data)
    destination = folder / "local" / "sources" / f"{paper['source_id']}_{digest}.{kind}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        destination.write_bytes(data)
    document = parse_document(destination, paper["paper_id"])
    source = {
        "path": str(destination.resolve()), "source_sha256": digest,
        "source_kind": kind, "origin": candidate["origin"], "url": final_url,
        "availability": "input_gap", "access_basis": candidate["basis"],
        "content_type": content_type, "retrieved_utc": now(),
        "parse_status": document["status"], "coverage": document["coverage"],
        "openalex_work_id": openalex_id,
    }
    if document["status"] not in {"readable", "readable_partial"}:
        source["availability"] = "input_gap"
        paper.setdefault("sources", []).append(source)
        return False
    source["availability"] = "local"
    paper.setdefault("sources", []).append(source)
    preference = {"xml": 0, "html": 1, "pdf": 2}
    if (not paper.get("path") or
            preference.get(kind, 99) < preference.get(paper.get("source_kind"), 99)):
        paper.update(path=str(destination.resolve()), source_sha256=digest,
                     source_kind=kind, source_format=kind, availability="local")
    return True


def fetch(inventory, limit=None, upgrade=False):
    folder = Path(inventory).resolve()
    papers = read(folder / "papers.json")
    summary = read(folder / "source_inventory.json")
    client, processed, downloaded = Client(), 0, 0
    for paper in papers:
        if limit is not None and processed >= limit:
            break
        if paper.get("path") and not (upgrade and paper.get("source_kind") in {"html", "pdf"}):
            continue
        processed += 1
        metadata = openalex_metadata(client, paper, allow_repeat=upgrade)
        if not metadata:
            summary["last_openalex_fetch"] = {"checked_utc": now(), "processed": processed,
                                               "downloaded": downloaded, "limit": limit}
            persist(folder, papers, summary)
            continue
        openalex_id = metadata.get("id")
        candidates_for_paper = [x for x in candidates(metadata)
                                if x["url"] not in historical_urls(paper)]
        got = False
        for candidate in candidates_for_paper:
            url = candidate["url"]
            try:
                data, final, content_type = client.get(url, accept="application/xml,text/html,application/pdf")
                attempt = append_attempt(paper, url, "openalex_oa_fulltext", "received",
                                         final_url=final, content_type=content_type,
                                         bytes=len(data), sha256=sha_bytes(data))
                if store(folder, paper, candidate, data, final, content_type, openalex_id):
                    attempt["parse_status"] = "readable"
                    got = True
                    downloaded += 1
                    break
                attempt["parse_status"] = "input_gap"
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                code = getattr(exc, "code", None)
                append_attempt(paper, url, "openalex_oa_fulltext",
                               "rate_limited" if code == 429 else
                               "access_denied" if code in {401, 402, 403} else
                               "request_failed", http_status=code,
                               error=f"{type(exc).__name__}: {exc}")
        if not got:
            if paper.get("path"):
                paper["availability"] = "local"
                paper["availability_reason"] = "existing_local_source_retained"
            else:
                paper["availability"] = "input_gap"
                paper["availability_reason"] = "openalex_has_no_new_readable_oa_location"
        else:
            paper["availability_reason"] = "openalex_public_oa_fulltext"
        summary["last_openalex_fetch"] = {"checked_utc": now(), "processed": processed,
                                           "downloaded": downloaded, "limit": limit}
        persist(folder, papers, summary)
        print({"paper_id": paper["paper_id"], "downloaded": got,
               "processed": processed, "download_count": downloaded}, flush=True)
    summary["last_openalex_fetch"] = {"checked_utc": now(), "processed": processed,
                                       "downloaded": downloaded, "limit": limit}
    persist(folder, papers, summary)
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--upgrade", action="store_true",
                        help="also inspect downloaded HTML/PDF papers for a better OA XML source")
    args = parser.parse_args()
    print(json.dumps(fetch(args.inventory, args.limit, args.upgrade), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
