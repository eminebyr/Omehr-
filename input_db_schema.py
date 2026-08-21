"""INPUT VERİ ŞEMASI — Excel'deki 62+ sayfanın PostgreSQL/SQLite tablo tanımı.

Tasarım kararı: her sütun basitçe TEXT olarak saklanır (Excel'in kendisi de
gevşek tipliydi — kod tabanı zaten her yerde `numeric()/txt()/req()` ile
tip zorlaması yapıyor, bkz. src/text_utils.py). Bu, 527 sütunun her biri
için elle tip belirlemek yerine TEK, tutarlı ve hataya dayanıklı bir
yaklaşımdır. Her tabloya ayrıca şunlar otomatik eklenir:
  - id: SERIAL/INTEGER PRIMARY KEY (satır kimliği, Excel satır sırasını korur)
  - _sira: orijinal Excel satır sırası (dışa aktarımda sırayı korumak için)
  - _guncelleyen, _guncelleme_zamani: web panelinden düzenleme denetim izi

Şema, gerçek input dosyasından (services/input_db_schema_data.json)
OTOMATİK türetilir — 62 sayfanın başlıklarını elle kopyalamak yerine.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_SEMA_DOSYASI = Path(__file__).resolve().parent / "input_db_schema_data.json"


def _tablo_adi(sheet_adi: str) -> str:
    """Excel sayfa adını güvenli bir SQL tablo adına çevirir."""
    s = sheet_adi.strip().lower()
    tr_harita = str.maketrans("çğıöşü ", "cgiosu_")
    s = s.translate(tr_harita)
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return f"in_{s}"


def _sutun_adi(baslik: str, kullanilan: set[str]) -> str:
    """Excel sütun başlığını güvenli bir SQL sütun adına çevirir; çakışırsa
    sayısal sonek ekler (bazı sayfalarda tekrar eden başlıklar olabilir)."""
    s = str(baslik).strip().lower()
    tr_harita = str.maketrans("çğıöşü", "cgiosu")
    s = s.translate(tr_harita)
    for ch in " ()/%.-'\"":
        s = s.replace(ch, "_")
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_") or "sutun"
    if s[0].isdigit():
        s = f"c_{s}"
    taban = s
    sayac = 2
    while s in kullanilan:
        s = f"{taban}_{sayac}"
        sayac += 1
    kullanilan.add(s)
    return s


def load_schema() -> dict[str, dict]:
    """{sheet_adi: {"tablo": str, "header_row": int, "kolonlar": [(excel_baslik, sql_adi), ...]}}"""
    with open(_SEMA_DOSYASI, encoding="utf-8") as f:
        ham = json.load(f)
    sonuc = {}
    for sheet_adi, bilgi in ham.items():
        tablo = _tablo_adi(sheet_adi)
        kullanilan: set[str] = set()
        kolonlar = []
        for baslik in bilgi["headers"]:
            if baslik is None:
                continue
            sql_adi = _sutun_adi(baslik, kullanilan)
            kolonlar.append((str(baslik), sql_adi))
        sonuc[sheet_adi] = {
            "tablo": tablo,
            "header_row": bilgi["header_row"],
            "kolonlar": kolonlar,
        }
    return sonuc


def create_table_ddl(tablo: str, kolonlar: list[tuple[str, str]], backend: str) -> str:
    """Bir sayfa için CREATE TABLE deyimini üretir (backend: 'sqlite' | 'postgres').

    DÜZELTME (SaaS/çok kiracılı temel): her tabloya artık bir tenant_id
    sütunu eklenir. Bu, TEK bir çalışan sunucunun (tek main.py/web
    süreci) oturuma göre BİRDEN FAZLA firmanın verisini AYNI veritabanı
    tablosunda, birbirine KARIŞMADAN tutabilmesinin temelidir — önceki
    "kiracı başına ayrı klasör/süreç" modelinden (services/tenant_manager.py)
    farklı olarak, gerçek SaaS'ta beklenen "paylaşılan veritabanı,
    tenant_id ile satır bazlı izolasyon" desenidir.
    """
    if backend == "postgres":
        id_tanimi = "id SERIAL PRIMARY KEY"
    else:
        id_tanimi = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    sabit_kolonlar = [
        id_tanimi,
        "tenant_id TEXT NOT NULL DEFAULT 'BASDAS'",
        "_sira INTEGER NOT NULL",
        "_guncelleyen TEXT",
        "_guncelleme_zamani TEXT",
    ]
    veri_kolonlari = [f'"{sql_adi}" TEXT' for _, sql_adi in kolonlar]
    tum_kolonlar = ", ".join(sabit_kolonlar + veri_kolonlari)
    return f'CREATE TABLE IF NOT EXISTS "{tablo}" ({tum_kolonlar})'


def create_tenant_index_ddl(tablo: str) -> str:
    """tenant_id üzerinde indeks — çok kiracılı sorgularda performans için."""
    return f'CREATE INDEX IF NOT EXISTS "idx_{tablo}_tenant" ON "{tablo}" (tenant_id)'
