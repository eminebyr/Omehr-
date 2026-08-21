from __future__ import annotations

import re
import unicodedata

_DATE_RE = re.compile(r"\b(\d{1,2}[./-]\d{1,2}[./-]\d{4})\b")

def _canon(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.casefold().strip()

def note_kind(note: object) -> str:
    """Ayrılış notlarını kırmızı, diğer personel notlarını sarı sınıfına ayırır."""
    key = _canon(note)
    if any(token in key for token in ("ayrilacak", "ayrılacak", "ayrilis", "ayrılış", "isten ayril", "işten ayrıl", "cikis yapacak", "çıkış yapacak", "cikisi", "çıkışı")):
        return "departure"
    return "info" if key else ""

def format_person_note(name: object, note: object) -> str:
    """Kullanıcı notunu raporda okunabilir, kişi bazlı cümleye dönüştürür."""
    person = str(name or "").strip()
    raw = str(note or "").strip().strip(".;")
    if not raw:
        return ""
    key = _canon(raw)
    date_match = _DATE_RE.search(raw)
    date = date_match.group(1).replace("/", ".").replace("-", ".") if date_match else ""
    if note_kind(raw) == "departure":
        return f"{person} {date + ' tarihinde ' if date else ''}ayrılacaktır."
    if "rapor" in key:
        if date:
            return f"{person} {date} tarihine kadar raporludur."
        return f"{person} raporludur."
    if "gezici" in key:
        return f"{person} gezicidir."
    # Kullanıcının yazdığı serbest metni koru; yalnız kişi adı ve noktalama ekle.
    if key.startswith(_canon(person)):
        sentence = raw
    else:
        sentence = f"{person} {raw}"
    return sentence[0].upper() + sentence[1:] + ("" if sentence.endswith((".", "!", "?")) else ".")
