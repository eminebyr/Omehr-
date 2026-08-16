from __future__ import annotations

"""Windows Outlook/Edge icin PDF gorunum sabitleme yardimcilari.

ReportLab TTF alt-kume fontlari bazi Windows PDF goruntuleyicilerinde harf
araliklari veya Turkce glif eslemesi bozuk gorunebilir. Bu modul, uretilen
PDF sayfalarini yuksek cozunurlukte rasterize edip ayni sayfa boyutlariyla
image-only PDF olarak yeniden yazar. Boylece gorunum tum goruntuleyicilerde
piksel olarak ayni kalir.
"""

from pathlib import Path
import os
import tempfile


def make_outlook_safe_pdf(path: str | Path, *, dpi: int = 180, jpeg_quality: int = 92) -> Path:
    """PDF'yi Outlook/Edge uyumlu image-only PDF olarak yerinde donusturur.

    Donusum atomik yapilir: basarisiz olursa orijinal PDF korunur.
    BASDAS_PDF_OUTLOOK_SAFE=0 ile devre disi birakilabilir.
    """
    target = Path(path)
    if os.getenv("BASDAS_PDF_OUTLOOK_SAFE", "1").strip().lower() in {"0", "false", "hayir", "no"}:
        return target
    if not target.is_file() or target.stat().st_size == 0:
        raise FileNotFoundError(f"PDF bulunamadi veya bos: {target}")

    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - kurulum sorunu
        raise RuntimeError(
            "Outlook uyumlu PDF icin PyMuPDF kurulu degil. "
            "KURULUM.bat dosyasini yeniden calistirin."
        ) from exc

    scale = max(1.0, float(dpi) / 72.0)
    matrix = fitz.Matrix(scale, scale)
    tmp = target.with_name(target.stem + ".outlook_safe.tmp.pdf")
    source = fitz.open(str(target))
    out = fitz.open()
    try:
        for page in source:
            pix = page.get_pixmap(matrix=matrix, alpha=False, colorspace=fitz.csRGB)
            image = pix.tobytes("jpeg", jpg_quality=int(jpeg_quality))
            rect = page.rect
            new_page = out.new_page(width=rect.width, height=rect.height)
            new_page.insert_image(new_page.rect, stream=image, keep_proportion=False)
        if out.page_count != source.page_count:
            raise RuntimeError("PDF sayfa sayisi donusum sirasinda degisti")
        out.save(str(tmp), garbage=4, deflate=True, clean=True)
    finally:
        out.close()
        source.close()

    if not tmp.is_file() or tmp.stat().st_size < 1024:
        tmp.unlink(missing_ok=True)
        raise RuntimeError("Outlook uyumlu PDF olusturulamadi")
    tmp.replace(target)
    return target
