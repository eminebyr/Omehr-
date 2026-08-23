from pathlib import Path

import fitz
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from services.pdf_compat import make_outlook_safe_pdf


def test_make_outlook_safe_pdf_preserves_pages_and_flattens_text(tmp_path: Path):
    pdf = tmp_path / "turkce.pdf"
    c = canvas.Canvas(str(pdf), pagesize=A4)
    c.drawString(72, 760, "OMEHR TEST")
    c.showPage()
    c.drawString(72, 760, "IKINCI SAYFA")
    c.save()

    make_outlook_safe_pdf(pdf, dpi=120, jpeg_quality=90)

    doc = fitz.open(str(pdf))
    assert doc.page_count == 2
    # Image-only cikti: Outlook/Edge font kodlamasini yorumlamaz.
    assert all(len(page.get_images(full=True)) >= 1 for page in doc)
    assert all(page.get_text("text").strip() == "" for page in doc)
    doc.close()
