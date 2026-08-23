from __future__ import annotations

from pathlib import Path


def test_pdf_fonts_use_windows_compatible_ascii_subset():
    from reportlab import rl_config
    from src.pdf_fonts import font

    assert rl_config.ttfAsciiReadable == 1
    assert font() == "OmehrPDF"
    assert font(True) == "OmehrPDF-Bold"


def test_pdf_font_files_are_packaged():
    from services.runtime_paths import runtime_root

    root = runtime_root()
    assert (root / "assets" / "fonts" / "DejaVuSans.ttf").stat().st_size > 100_000
    assert (root / "assets" / "fonts" / "DejaVuSans-Bold.ttf").stat().st_size > 100_000
