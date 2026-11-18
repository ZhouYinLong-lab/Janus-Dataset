from pathlib import Path

import fitz
import requests
from bs4 import BeautifulSoup
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parent
STAGING = ROOT / "staging"
STAGING.mkdir(parents=True, exist_ok=True)


def copy_pdf(src: Path, dst: Path) -> None:
    data = src.read_bytes()
    if data[:4] != b"%PDF":
        raise RuntimeError(f"not a PDF: {src}")
    dst.write_bytes(data)


# 07: PMC's download endpoint uses a proof-of-work cookie; 07-pow.pdf is the
# verified download produced by the intake script.
copy_pdf(STAGING / "07-pow.pdf", STAGING / "07.pdf")


# 09: retain the LIT-PCBA chapter from the author's openly available thesis.
# This is explicitly an author-version chapter, not a silent substitute for
# the ACS journal PDF.
thesis = fitz.open(STAGING / "test_09b.bin")
out = fitz.open()
for page_no in range(138, 161):
    out.insert_pdf(thesis, from_page=page_no, to_page=page_no)
out.set_metadata(
    {
        "title": "LIT-PCBA: An Unbiased Data Set for Machine Learning and Virtual Screening (thesis chapter)",
        "author": "Viet-Khoa Tran-Nguyen",
        "subject": "Open author-version chapter corresponding to the LIT-PCBA work",
        "keywords": "LIT-PCBA; inactive compounds; virtual screening; thesis chapter",
    }
)
out.save(STAGING / "09.pdf")
out.close()
thesis.close()


# 05: make a clearly labelled local reading PDF from the freely accessible
# publisher landing page. The article PDF requires institutional access here.
url = "https://www.nature.com/articles/nbt.3374"
html = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
html.raise_for_status()
soup = BeautifulSoup(html.text, "html.parser")
for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
    tag.decompose()
main = soup.find("main") or soup.body
text = (main or soup).get_text("\n", strip=True)
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleCenter", parent=styles["Title"], alignment=TA_CENTER, fontSize=16, leading=20, spaceAfter=12))
styles.add(ParagraphStyle(name="Notice", parent=styles["BodyText"], borderWidth=0.5, borderColor="#888888", backColor="#f4f4f4", borderPadding=8, leading=14, spaceAfter=12))
story = [
    Paragraph("Comprehensive characterization of the Published Kinase Inhibitor Set", styles["TitleCenter"]),
    Paragraph("Local reading export — not the publisher PDF. The Nature article PDF was not downloadable without institutional authentication at intake. This file preserves the accessible publisher landing-page metadata and abstract; the stable article link remains attached.", styles["Notice"]),
]
for block in [part.strip() for part in text.split("\n") if part.strip()]:
    story.append(Paragraph(block.replace("&", "&amp;"), styles["BodyText"]))
    story.append(Spacer(1, 0.18 * cm))
SimpleDocTemplate(str(STAGING / "05.pdf"), pagesize=A4, rightMargin=1.8 * cm, leftMargin=1.8 * cm, topMargin=1.8 * cm, bottomMargin=1.8 * cm).build(story)


for name in ("05.pdf", "07.pdf", "09.pdf"):
    path = STAGING / name
    data = path.read_bytes()
    print(f"{path.name}: {len(data)} bytes; {data[:4]!r}")
