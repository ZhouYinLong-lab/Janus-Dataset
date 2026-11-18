"""Fetch Crossref links only when Crossref exposes an explicit CC/OA license."""
import argparse
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from corpus import read
from fetch_openalex_oa import Client, historical_urls, normalize_url, persist, sha_bytes, store

CROSSREF = "https://api.crossref.org/works/"
CC = re.compile(r"creativecommons\.org|open.?access", re.I)


def licensed_candidates(message):
    licenses = [str(x.get("URL", "")) for x in (message.get("license") or [])]
    if not any(CC.search(x) for x in licenses):
        return []
    result, seen = [], set()
    for link in message.get("link") or []:
        url = normalize_url(link.get("URL"))
        if not url or url in seen:
            continue
        content_type = str(link.get("content-type") or "").lower()
        kind = "pdf" if "pdf" in content_type or "/pdf" in url.lower() else "html"
        result.append({"url": url, "kind": kind,
                       "basis": "Crossref explicit CC/Open Access license: " + ";".join(licenses),
                       "origin": "crossref_licensed_link"})
        seen.add(url)
    return result


def crossref(client, paper):
    doi = paper.get("doi")
    if not doi:
        return None
    url = CROSSREF + __import__("urllib.parse").parse.quote(doi, safe="")
    try:
        data, final, content_type = client.get(url)
        payload = json.loads(data.decode("utf-8"))
        message = payload.get("message") or {}
        returned = str(message.get("DOI", "")).lower().rstrip("/")
        if returned != doi.lower().rstrip("/"):
            paper.setdefault("fetch_attempts", []).append({"url": url, "purpose": "crossref_search",
                "started_utc": __import__("fetch_openalex_oa").now(), "status": "identity_mismatch",
                "crossref_doi": message.get("DOI")})
            return None
        paper.setdefault("fetch_attempts", []).append({"url": url, "purpose": "crossref_search",
            "started_utc": __import__("fetch_openalex_oa").now(), "status": "received",
            "final_url": final, "content_type": content_type, "bytes": len(data),
            "sha256": sha_bytes(data)})
        return message
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        paper.setdefault("fetch_attempts", []).append({"url": url, "purpose": "crossref_search",
            "started_utc": __import__("fetch_openalex_oa").now(),
            "status": "rate_limited" if getattr(exc, "code", None) == 429 else "request_failed",
            "http_status": getattr(exc, "code", None), "error": f"{type(exc).__name__}: {exc}"})
        return None


def fetch(inventory, limit=None):
    folder = Path(inventory).resolve()
    papers, summary = read(folder / "papers.json"), read(folder / "source_inventory.json")
    client, processed, downloaded = Client(), 0, 0
    for paper in papers:
        if limit is not None and processed >= limit:
            break
        if paper.get("path"):
            continue
        processed += 1
        message = crossref(client, paper)
        if message:
            for candidate in licensed_candidates(message):
                if candidate["url"] in historical_urls(paper):
                    continue
                try:
                    data, final, content_type = client.get(
                        candidate["url"], accept="application/pdf,text/html,application/xml")
                    attempt = {"url": candidate["url"], "purpose": "crossref_licensed_fulltext",
                               "started_utc": __import__("fetch_openalex_oa").now(), "status": "received",
                               "final_url": final, "content_type": content_type,
                               "bytes": len(data), "sha256": sha_bytes(data)}
                    paper.setdefault("fetch_attempts", []).append(attempt)
                    if store(folder, paper, candidate, data, final, content_type, None):
                        attempt["parse_status"] = "readable"
                        downloaded += 1
                        break
                    attempt["parse_status"] = "input_gap"
                except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                    paper.setdefault("fetch_attempts", []).append({
                        "url": candidate["url"], "purpose": "crossref_licensed_fulltext",
                        "started_utc": __import__("fetch_openalex_oa").now(),
                        "status": "access_denied" if getattr(exc, "code", None) in {401, 402, 403}
                                  else "rate_limited" if getattr(exc, "code", None) == 429
                                  else "request_failed",
                        "http_status": getattr(exc, "code", None),
                        "error": f"{type(exc).__name__}: {exc}"})
        if not paper.get("path"):
            paper["availability"] = "input_gap"
            paper["availability_reason"] = "no_new_crossref_cc_fulltext"
        else:
            paper["availability"] = "local"
        summary["last_crossref_fetch"] = {"processed": processed, "downloaded": downloaded,
                                           "limit": limit, "checked_utc": __import__("fetch_openalex_oa").now()}
        persist(folder, papers, summary)
        print({"paper_id": paper["paper_id"], "downloaded": bool(paper.get("path")),
               "processed": processed, "download_count": downloaded}, flush=True)
    summary["last_crossref_fetch"] = {"processed": processed, "downloaded": downloaded,
                                       "limit": limit, "checked_utc": __import__("fetch_openalex_oa").now()}
    persist(folder, papers, summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(fetch(args.inventory, args.limit), ensure_ascii=False, indent=2))
