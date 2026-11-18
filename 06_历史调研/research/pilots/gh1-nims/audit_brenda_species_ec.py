"""Check BRENDA's public species page for EC coverage of one pilot record.

This is a species-level scoping check only; it cannot establish accession- or
assay-row-level absence from BRENDA.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.request import Request, urlopen


URL = "https://brenda-enzymes.org/organism.php?organism=Bacillus%20licheniformis"
TARGET_EC = "3.2.1.21"


class VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def main() -> None:
    request = Request(URL, headers={"User-Agent": "Janus-Dataset research audit/1.0"})
    with urlopen(request, timeout=30) as response:
        raw = response.read()

    parser = VisibleText()
    parser.feed(raw.decode("utf-8", errors="replace"))
    text = " ".join(parser.parts)
    normalized_text = re.sub(r"\s+", " ", text).strip()
    ec_numbers = sorted(set(re.findall(r"\bEC\s+(\d+\.\d+\.\d+\.(?:\d+|B\d+))\b", text)))

    print(f"retrieved_utc={datetime.now(timezone.utc).isoformat()}")
    print(f"url={URL}")
    print(f"response_bytes={len(raw)}")
    print(f"response_sha256={hashlib.sha256(raw).hexdigest().upper()}")
    print(f"normalized_visible_text_sha256={hashlib.sha256(normalized_text.encode('utf-8')).hexdigest().upper()}")
    print(f"unique_ec_entries={len(ec_numbers)}")
    print(f"target_ec={TARGET_EC}")
    print(f"target_ec_present={TARGET_EC in ec_numbers}")
    print("beta_glucosidase_adjacent_ec_entries=" + ",".join(
        ec for ec in ec_numbers if ec.startswith("3.2.1.")
    ))
    print("interpretation=species-level page check only; not proof of exact accession or assay-row absence")


if __name__ == "__main__":
    main()
