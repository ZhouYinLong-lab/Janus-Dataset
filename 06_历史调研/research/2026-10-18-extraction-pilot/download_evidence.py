"""Retain available publisher PDFs, one figure and relevant supplements."""

from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
from pathlib import Path
import zipfile

import requests

HERE = Path(__file__).resolve().parent
SOURCES = HERE / "sources"
TARGETS = [
    ("32522206.pdf", "https://link.springer.com/content/pdf/10.1186/s12934-020-01386-1.pdf", "pdf"),
    ("33471829.pdf", "https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0241325&type=printable", "pdf"),
    ("35464910.pdf", "https://www.frontiersin.org/journals/microbiology/articles/10.3389/fmicb.2022.860014/pdf", "pdf"),
    ("32522206_supplement.docx", "https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs12934-020-01386-1/MediaObjects/12934_2020_1386_MOESM1_ESM.docx", "zip"),
    ("35464910_figure6.webp", "https://www.frontiersin.org/files/Articles/860014/xml-images/fmicb-13-860014-g006.webp", "webp"),
    ("35464910_supplementary.zip", "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC9024363/supplementaryFiles", "zip"),
]


def download(item):
    name, url, expected = item
    row = dict(file=name, url=url, status="failed", bytes=0, sha256="", reason="")
    try:
        path = SOURCES / name
        if path.exists():
            data = path.read_bytes()
        else:
            response = requests.get(url, timeout=40, headers={"User-Agent": "Janus-Dataset research/1.0"})
            response.raise_for_status()
            data = response.content
        valid = ((expected == "pdf" and data.startswith(b"%PDF")) or
                 (expected == "zip" and data.startswith(b"PK")) or
                 (expected == "webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"))
        if not valid:
            raise ValueError(f"Unexpected response signature: {data[:40]!r}")
        path.write_bytes(data)
        row.update(status="downloaded", bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        if name.endswith("supplementary.zip"):
            with zipfile.ZipFile(path) as archive:
                for member in archive.namelist():
                    if Path(member).name == "Data_Sheet_1.docx":
                        (SOURCES / "35464910_supplement.docx").write_bytes(archive.read(member))
    except Exception as error:
        row["reason"] = str(error)
    print(f"{name}: {row['status']}; {row['bytes']} bytes", flush=True)
    return row


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(download, TARGETS))
    with (HERE / "evidence_downloads.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
