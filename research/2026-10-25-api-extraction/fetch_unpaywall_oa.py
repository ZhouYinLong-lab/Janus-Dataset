"""Fetch Unpaywall OA locations for unresolved DOI records."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError

from corpus import read
from fetch_openalex_oa import Client, historical_urls, normalize_url, persist, sha_bytes, store, now

API = "https://api.unpaywall.org/v2/"


def candidates(payload):
    if payload.get("is_oa") is not True:
        return []
    locations = []
    best = payload.get("best_oa_location")
    if isinstance(best, dict):
        locations.append(best)
    locations.extend(x for x in (payload.get("oa_locations") or [])
                     if isinstance(x, dict) and x is not best)
    result, seen = [], set()
    for location in locations:
        pdf = normalize_url(location.get("url_for_pdf"))
        landing = normalize_url(location.get("url_for_landing_page"))
        basis = "Unpaywall is_oa=true; host_type=" + str(location.get("host_type") or "unknown")
        if location.get("license"):
            basis += "; license=" + str(location["license"])
        if pdf and pdf not in seen:
            result.append({"url": pdf, "kind": "pdf", "basis": basis,
                           "origin": "unpaywall_oa_location"})
            seen.add(pdf)
        if landing and landing not in seen and "doi.org/" not in landing:
            result.append({"url": landing, "kind": "html", "basis": basis,
                           "origin": "unpaywall_oa_location"})
            seen.add(landing)
    return result


def lookup(client, paper, email):
    doi = paper.get("doi")
    if not doi:
        return None
    url = API + quote(doi, safe="") + "?email=" + quote(email, safe="@+.")
    try:
        data, final, content_type = client.get(url)
        payload = json.loads(data.decode("utf-8"))
        returned = str(payload.get("doi", "")).lower().rstrip("/")
        if returned != doi.lower().rstrip("/"):
            paper.setdefault("fetch_attempts", []).append({"url": url, "purpose": "unpaywall_search",
                "started_utc": now(), "status": "identity_mismatch", "unpaywall_doi": payload.get("doi")})
            return None
        paper.setdefault("fetch_attempts", []).append({"url": url, "purpose": "unpaywall_search",
            "started_utc": now(), "status": "received", "final_url": final,
            "content_type": content_type, "bytes": len(data), "sha256": sha_bytes(data)})
        return payload
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        paper.setdefault("fetch_attempts", []).append({"url": url, "purpose": "unpaywall_search",
            "started_utc": now(), "status": "rate_limited" if getattr(exc, "code", None) == 429 else "request_failed",
            "http_status": getattr(exc, "code", None), "error": f"{type(exc).__name__}: {exc}"})
        return None


def fetch(inventory, email, limit=None):
    folder = Path(inventory).resolve()
    papers, summary = read(folder / "papers.json"), read(folder / "source_inventory.json")
    client, processed, downloaded = Client(), 0, 0
    for paper in papers:
        if limit is not None and processed >= limit:
            break
        if paper.get("path"):
            continue
        processed += 1
        payload = lookup(client, paper, email)
        if payload:
            for candidate in candidates(payload):
                if candidate["url"] in historical_urls(paper):
                    continue
                try:
                    data, final, content_type = client.get(candidate["url"], accept="application/pdf,text/html,application/xml")
                    attempt = {"url": candidate["url"], "purpose": "unpaywall_oa_fulltext",
                               "started_utc": now(), "status": "received", "final_url": final,
                               "content_type": content_type, "bytes": len(data), "sha256": sha_bytes(data)}
                    paper.setdefault("fetch_attempts", []).append(attempt)
                    if store(folder, paper, candidate, data, final, content_type, None):
                        attempt["parse_status"] = "readable"
                        downloaded += 1
                        break
                    attempt["parse_status"] = "input_gap"
                except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                    paper.setdefault("fetch_attempts", []).append({
                        "url": candidate["url"], "purpose": "unpaywall_oa_fulltext", "started_utc": now(),
                        "status": "access_denied" if getattr(exc, "code", None) in {401, 402, 403}
                                  else "rate_limited" if getattr(exc, "code", None) == 429 else "request_failed",
                        "http_status": getattr(exc, "code", None), "error": f"{type(exc).__name__}: {exc}"})
        if not paper.get("path"):
            paper["availability"] = "input_gap"
            paper["availability_reason"] = "no_new_unpaywall_oa_fulltext"
        else:
            paper["availability"] = "local"
        summary["last_unpaywall_fetch"] = {"processed": processed, "downloaded": downloaded,
                                            "limit": limit, "checked_utc": now()}
        persist(folder, papers, summary)
        print({"paper_id": paper["paper_id"], "downloaded": bool(paper.get("path")),
               "processed": processed, "download_count": downloaded}, flush=True)
    summary["last_unpaywall_fetch"] = {"processed": processed, "downloaded": downloaded,
                                        "limit": limit, "checked_utc": now()}
    persist(folder, papers, summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--email", required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    print(json.dumps(fetch(args.inventory, args.email, args.limit), ensure_ascii=False, indent=2))
