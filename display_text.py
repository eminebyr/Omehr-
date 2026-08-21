from __future__ import annotations

import unicodedata


def display_text(value: object) -> str:
    """Return visible UI text in canonical NFC Unicode without transliteration."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFC", text)
    return "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")


MAIN_TITLE = display_text("OMEHR Norm Kadro, Transfer ve İş Gücü Optimizasyon Platformu")
