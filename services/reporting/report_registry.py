from __future__ import annotations

"""Report Registry — aynı raporun/belgenin fiziksel olarak İKİNCİ KEZ
üretilmesini engeller (OMEHR hızlandırma şartnamesi Madde 22-24).

Anahtar: report_type + scope_type + scope_id + data_version +
template_version + format. Aynı anahtarla bir kayıt zaten varsa VE
dosya hâlâ diskte duruyorsa, YENİDEN ÜRETMEK yerine mevcut dosya
kullanılır.

Not: Madde 18 (Atama Evrakı dedup) BU modülü kullanır — ayrı, paralel
bir dedup mekanizması yazılmadı.
"""

import hashlib
import json
import sqlite3
from pathlib import Path


def _db_path(root: Path) -> Path:
    p = Path(root) / "data" / "report_registry.db"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _connect(root: Path) -> sqlite3.Connection:
    con = sqlite3.connect(_db_path(root))
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS report_registry(
        key TEXT PRIMARY KEY,
        report_type TEXT, scope_type TEXT, scope_id TEXT,
        data_version TEXT, template_version TEXT, format TEXT,
        file_path TEXT, created_at TEXT, duration_ms INTEGER
    )""")
    con.commit()
    return con


def build_key(*, report_type: str, scope_type: str, scope_id: str,
              data_version: str, template_version: str = "V1", format: str = "PDF") -> str:
    raw = f"{report_type}|{scope_type}|{scope_id}|{data_version}|{template_version}|{format}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def find_existing(root: Path, key: str) -> str | None:
    """Bu anahtarla ÖNCEDEN üretilmiş VE hâlâ diskte duran bir dosya
    varsa yolunu döner; yoksa None (yeniden üretilmeli)."""
    con = _connect(root)
    try:
        row = con.execute("SELECT file_path FROM report_registry WHERE key=?", (key,)).fetchone()
        if row and Path(row["file_path"]).is_file():
            return row["file_path"]
        return None
    finally:
        con.close()


def register(root: Path, *, key: str, report_type: str, scope_type: str, scope_id: str,
             data_version: str, template_version: str, format: str, file_path: str,
             duration_ms: int = 0) -> None:
    from datetime import datetime
    con = _connect(root)
    try:
        con.execute(
            """INSERT OR REPLACE INTO report_registry
               (key, report_type, scope_type, scope_id, data_version, template_version, format, file_path, created_at, duration_ms)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (key, report_type, scope_type, scope_id, data_version, template_version, format,
             str(file_path), datetime.now().isoformat(timespec="seconds"), duration_ms),
        )
        con.commit()
    finally:
        con.close()


def get_or_build(root: Path, *, report_type: str, scope_type: str, scope_id: str,
                  data_version: str, template_version: str, format: str, builder) -> tuple[str, bool]:
    """(dosya_yolu, yeniden_uretildi_mi) döner.

    `builder`, dosyayı GERÇEKTEN üreten (parametresiz) bir çağrılabilir —
    yalnız bu anahtar için kayıtlı bir dosya YOKSA çağrılır."""
    import time
    key = build_key(report_type=report_type, scope_type=scope_type, scope_id=scope_id,
                     data_version=data_version, template_version=template_version, format=format)
    mevcut = find_existing(root, key)
    if mevcut:
        return mevcut, False
    t0 = time.perf_counter()
    yol = builder()
    sure_ms = int((time.perf_counter() - t0) * 1000)
    register(root, key=key, report_type=report_type, scope_type=scope_type, scope_id=scope_id,
             data_version=data_version, template_version=template_version, format=format,
             file_path=str(yol), duration_ms=sure_ms)
    return str(yol), True
