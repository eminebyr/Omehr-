"""SQLite -> PostgreSQL VERİ TAŞIMA ARACI.

Mevcut SQLite veritabanlarındaki (data/v16_management.db,
data/security.db, ...) tabloları, şemalarını SQLite'tan OKUYARAK
otomatik türeten ve PostgreSQL'de yeniden oluşturup verileri kopyalayan
genel amaçlı bir araçtır. Elle DDL yazmak yerine `PRAGMA table_info`
kullanır — bu sayede yeni bir sütun eklendiğinde bu aracın
güncellenmesi gerekmez.

Kullanım (main.py'den veya elle):
    from services.db_migration import migrate_database
    sonuc = migrate_database(
        sqlite_path=Path("data/v16_management.db"),
        postgres_dsn="postgresql://kullanici:parola@sunucu:5432/basdas",
    )
    print(sonuc)  # {'audit_log': {'sqlite_satir': 42, 'postgres_satir': 42, 'eslesti': True}, ...}

ÖNEMLİ SINIRLAR (dürüstçe):
- Bu araç VERİYİ taşır; UNIQUE/FOREIGN KEY kısıtlarını veya
  services/web_runtime.py'deki immutability TRIGGER'larını YENİDEN
  OLUŞTURMAZ (bunlar tabloya özel — bkz. services/db_backend.py modül
  docstring'i, "BİLEREK YAPILMAYAN" bölümü).
- Yalnız EK (INSERT) yapar; hedef tabloda aynı id'li satır zaten varsa
  atlar (ON CONFLICT DO NOTHING) — tekrar tekrar güvenle çalıştırılabilir.
- Gerçek bir PostgreSQL sunucusuna karşı (services/db_backend.py'nin
  test edildiği aynı canlı sunucu) test edilmiştir.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from services.exceptions import WorkbookError

_SQLITE_TO_PG_TYPE = {
    "INTEGER": "BIGINT",
    "TEXT": "TEXT",
    "REAL": "DOUBLE PRECISION",
    "BLOB": "BYTEA",
    "NUMERIC": "NUMERIC",
}


def _pg_column_type(sqlite_type: str) -> str:
    base = (sqlite_type or "TEXT").split("(")[0].strip().upper()
    return _SQLITE_TO_PG_TYPE.get(base, "TEXT")


def _sqlite_tables(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return [r[0] for r in rows]


def migrate_database(
    sqlite_path: Path, postgres_dsn: str, tables: list[str] | None = None
) -> dict[str, dict[str, Any]]:
    """sqlite_path'teki (var olan) tabloları PostgreSQL'e kopyalar.

    tables: yalnız belirli tabloları taşımak için isim listesi; None ise
    veritabanındaki TÜM kullanıcı tabloları taşınır.

    Dönüş: her tablo için {'sqlite_satir', 'postgres_satir', 'eslesti'}.
    """
    try:
        import psycopg2
        from psycopg2.extras import execute_values
    except ImportError as exc:
        raise WorkbookError(
            "PostgreSQL taşıması için psycopg2 gerekli: 'pip install psycopg2-binary'"
        ) from exc

    sqlite_path = Path(sqlite_path)
    if not sqlite_path.is_file():
        raise WorkbookError(f"Kaynak SQLite dosyası bulunamadı: {sqlite_path}")

    s_con = sqlite3.connect(sqlite_path)
    s_con.row_factory = sqlite3.Row
    pg_con = psycopg2.connect(postgres_dsn)

    sonuclar: dict[str, dict[str, Any]] = {}
    try:
        hedef_tablolar = tables if tables is not None else _sqlite_tables(s_con)
        for tablo in hedef_tablolar:
            kolon_bilgisi = s_con.execute(f"PRAGMA table_info({tablo})").fetchall()
            if not kolon_bilgisi:
                sonuclar[tablo] = {"hata": "SQLite'ta bulunamadı"}
                continue
            kolonlar = [k["name"] for k in kolon_bilgisi]
            pk_kolonlar = [k["name"] for k in kolon_bilgisi if k["pk"]]

            # PostgreSQL'de tablo yoksa oluştur (varsa DOKUNMA — mevcut
            # trigger/kısıt tanımını bozmamak için).
            pg_cur = pg_con.cursor()
            pg_cur.execute(
                "SELECT to_regclass(%s)", (tablo,)
            )
            var_mi = pg_cur.fetchone()[0] is not None
            if not var_mi:
                kolon_tanimlari = ", ".join(
                    f'"{k["name"]}" {_pg_column_type(k["type"])}' for k in kolon_bilgisi
                )
                pk_ifadesi = f', PRIMARY KEY ({", ".join(pk_kolonlar)})' if pk_kolonlar else ""
                pg_cur.execute(f'CREATE TABLE "{tablo}" ({kolon_tanimlari}{pk_ifadesi})')
                pg_con.commit()

            satirlar = s_con.execute(f"SELECT * FROM {tablo}").fetchall()
            sqlite_sayi = len(satirlar)

            if satirlar:
                kolon_listesi = ", ".join(f'"{k}"' for k in kolonlar)
                degerler = [tuple(row[k] for k in kolonlar) for row in satirlar]
                celisme_ifadesi = (
                    f'ON CONFLICT ({", ".join(pk_kolonlar)}) DO NOTHING' if pk_kolonlar else ""
                )
                execute_values(
                    pg_cur,
                    f'INSERT INTO "{tablo}" ({kolon_listesi}) VALUES %s {celisme_ifadesi}',
                    degerler,
                )
                pg_con.commit()

            pg_cur.execute(f'SELECT COUNT(*) FROM "{tablo}"')
            pg_sayi = pg_cur.fetchone()[0]
            sonuclar[tablo] = {
                "sqlite_satir": sqlite_sayi,
                "postgres_satir": pg_sayi,
                "eslesti": pg_sayi >= sqlite_sayi,
            }
    finally:
        s_con.close()
        pg_con.close()

    return sonuclar
