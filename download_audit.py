from __future__ import annotations

"""
İNDİRİLEN RAPOR KAYDI (KVKK — denetlenebilirlik)
====================================================
Pakette personel adı, adres, koordinat, performans skoru ve transfer bilgisi
gibi kişisel veriler bulunduğu için, HANGİ kullanıcının HANGİ raporu NE ZAMAN
indirdiğinin kalıcı bir kaydı tutulmalıdır — bu, veri ihlali/sızıntı
şüphesinde "bu dosyayı kim indirmiş?" sorusuna cevap verebilmek için
gereklidir.
"""

import sqlite3
from datetime import datetime

from services.runtime_paths import runtime_root
from services.safe_exec import log_swallowed

def _db_path():
    from services.runtime_paths import runtime_root
    return runtime_root() / "data" / "download_audit.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS indirme_kayitlari (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kullanici TEXT NOT NULL,
    rol TEXT,
    dosya_adi TEXT NOT NULL,
    zaman TEXT NOT NULL
)
"""


def _connect() -> sqlite3.Connection:
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_db_path(), timeout=30)
    con.execute(_SCHEMA)
    return con


def kaydet(kullanici: str, dosya_adi: str, rol: str = "") -> None:
    """Bir rapor indirme olayını kaydeder. Hata durumunda sessizce başarısız
    olur (indirme deneyimini ASLA bozmaz), ama loglar."""
    try:
        con = _connect()
        con.execute(
            "INSERT INTO indirme_kayitlari (kullanici, rol, dosya_adi, zaman) VALUES (?,?,?,?)",
            (kullanici or "bilinmiyor", rol or "", dosya_adi, datetime.now().isoformat(timespec="seconds")),
        )
        con.commit()
        con.close()
    except Exception as exc:
        from services.safe_exec import log_swallowed
        log_swallowed(f"download_audit.kaydet: '{dosya_adi}' indirme kaydı yazılamadı", exc)


def son_kayitlar(n: int = 200) -> list[dict]:
    """Denetim/gözlemlenebilirlik için son N indirme kaydını döndürür."""
    try:
        con = _connect()
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM indirme_kayitlari ORDER BY zaman DESC LIMIT ?", (n,)
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception as _exc:
        log_swallowed("services.download_audit.son_kayitlar: beklenmeyen hata", _exc)
        return []
