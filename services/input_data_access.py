"""INPUT VERİ ERİŞİM KATMANI — Excel yerine veritabanından oku/yaz.

Amaç: src/data_loading.py::load() içindeki `sheets=read_all(p)` çağrısının
YERİNE geçebilecek, AYNI ŞEKİLLİ (dict[str, pandas.DataFrame], sütun adları
ve sırası Excel'deki ile BİREBİR aynı) bir sonuç üreten fonksiyonlar sağlar.
Böylece state_engine.py, kpi_engine.py, ai_operations_engine.py gibi 30'dan
fazla modülün HİÇBİRİ değiştirilmeden, girdi kaynağı Excel'den PostgreSQL'e
taşınabilir (bkz. services/db_backend.py'nin aynı felsefeyle
web_runtime.py/management_center.py için uyguladığı desen).

Hangi backend'in kullanılacağı services/db_backend.py::backend_name() ile
aynı ortam değişkenleriyle (OMEHR_DB_BACKEND=sqlite|postgres) belirlenir.
Girdinin Excel mi veritabanı mı olduğu AYRI bir bayrakla kontrol edilir:

    OMEHR_INPUT_SOURCE=excel   (varsayılan — mevcut davranış, HİÇBİR ŞEY BOZULMAZ)
    OMEHR_INPUT_SOURCE=db      (yeni — bu modül devreye girer)

DÜZELTME (SaaS/çok kiracılı temel): tüm okuma/yazma fonksiyonları artık
tenant_id ile SATIR BAZLI filtrelenir. tenant_id parametresi verilmezse
services/tenant_context.py::current_tenant_id() ile OTURUMDAN (veya
OMEHR_TENANT ortam değişkeninden) otomatik çözümlenir.

KRİTİK DÜZELTME: write_sheet() önceden `DELETE FROM tablo` ile TÜM
kiracıların TÜM satırlarını siliyordu (yalnız DataFrame'deki satırları
yeniden ekliyordu) — çok kiracılı bir ortamda bu, BİR kiracının kaydet
işleminin TÜM DİĞER kiracıların verisini yok etmesi anlamına gelirdi.
Artık yalnız `DELETE FROM tablo WHERE tenant_id=?` (yalnız KENDİ
kiracısının satırları) silinir.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd

from services.db_backend import connect, backend_name
from services.input_db_schema import load_schema, create_table_ddl, create_tenant_index_ddl
from services.runtime_paths import runtime_root
from services.tenant_context import current_tenant_id


def input_source() -> str:
    v = os.environ.get("OMEHR_INPUT_SOURCE", "excel").strip().lower()
    if v not in {"excel", "db"}:
        v = "excel"
    return v


def _sqlite_path():
    return runtime_root() / "data" / "input_data.db"


def ensure_schema() -> None:
    """Tüm 62+ sayfa için tablo yoksa oluşturur (idempotent), tenant_id
    indeksini de kurar."""
    sema = load_schema()
    backend = backend_name()
    con = connect(_sqlite_path())
    try:
        for sheet_adi, bilgi in sema.items():
            ddl = create_table_ddl(bilgi["tablo"], bilgi["kolonlar"], backend)
            con.execute(ddl)
            con.execute(create_tenant_index_ddl(bilgi["tablo"]))
        con.commit()
    finally:
        con.close()


def read_sheet(sheet_adi: str, tenant_id: str | None = None) -> pd.DataFrame:
    """Tek bir sayfayı, Excel'deki sütun adı/sırasıyla BİREBİR aynı şekilde,
    YALNIZ belirtilen (veya oturumdan çözümlenen) kiracının satırlarını
    veritabanından okur."""
    tenant_id = (tenant_id or current_tenant_id()).strip().upper()
    sema = load_schema()
    if sheet_adi not in sema:
        return pd.DataFrame()
    bilgi = sema[sheet_adi]
    tablo = bilgi["tablo"]
    kolonlar = bilgi["kolonlar"]
    con = connect(_sqlite_path())
    try:
        sql_kolon_listesi = ", ".join(f'"{sql}"' for _, sql in kolonlar)
        try:
            rows = con.execute(
                f'SELECT {sql_kolon_listesi} FROM "{tablo}" WHERE tenant_id=? ORDER BY _sira',
                (tenant_id,),
            ).fetchall()
        except Exception:
            return pd.DataFrame(columns=[excel for excel, _ in kolonlar])
        veri = [dict(zip([excel for excel, _ in kolonlar], row)) for row in rows]
        df = pd.DataFrame(veri, columns=[excel for excel, _ in kolonlar])
        return df
    finally:
        con.close()


def read_all_sheets(tenant_id: str | None = None) -> dict[str, pd.DataFrame]:
    """common_veri_okuma.py::read_all()'ın DB tabanlı eşdeğeri — TÜM
    sayfaları aynı anda, aynı dict[str, DataFrame] şekliyle, YALNIZ
    belirtilen kiracı için döner."""
    tenant_id = (tenant_id or current_tenant_id()).strip().upper()
    sema = load_schema()
    return {sheet_adi: read_sheet(sheet_adi, tenant_id=tenant_id) for sheet_adi in sema}


def write_sheet(sheet_adi: str, df: pd.DataFrame, kullanici: str = "", tenant_id: str | None = None) -> int:
    """Bir DataFrame'i (web panelinden düzenlenmiş) tabloya YENİDEN YAZAR —
    ama YALNIZ bu kiracının SATIRLARINI siler/yeniden ekler; diğer
    kiracıların satırlarına ASLA dokunulmaz. Dönüş: yazılan satır sayısı.

    NOT: Denetim izi için her satıra _guncelleyen/_guncelleme_zamani eklenir.
    """
    tenant_id = (tenant_id or current_tenant_id()).strip().upper()
    sema = load_schema()
    if sheet_adi not in sema:
        raise ValueError(f"Bilinmeyen sayfa: {sheet_adi}")

    # DÜZELTME (SaaS kota uygulaması): sube_kotasi/kullanici_kotasi
    # önceden yalnız services/tenant_registry.py'de SAKLANIYORDU, hiçbir
    # yerde SAYILIP KARŞILAŞTIRILMIYORDU. Aşım varsa write burada,
    # transaction'a hiç başlamadan reddedilir.
    from services.tenant_quota import enforce_for_sheet
    enforce_for_sheet(sheet_adi, df, tenant_id)

    bilgi = sema[sheet_adi]
    tablo = bilgi["tablo"]
    kolonlar = bilgi["kolonlar"]
    zaman = datetime.now(timezone.utc).isoformat(timespec="seconds")

    con = connect(_sqlite_path())
    try:
        con.execute(f'DELETE FROM "{tablo}" WHERE tenant_id=?', (tenant_id,))
        sql_adlar = [sql for _, sql in kolonlar]
        tum_sql_kolonlar = ["tenant_id", "_sira", "_guncelleyen", "_guncelleme_zamani"] + sql_adlar
        yer_tutucular = ", ".join(["?"] * len(tum_sql_kolonlar))
        kolon_ifadesi = ", ".join(f'"{k}"' for k in tum_sql_kolonlar)
        yazilan = 0
        for sira, (_, satir) in enumerate(df.iterrows()):
            degerler = [tenant_id, sira, kullanici, zaman]
            for excel_baslik, _ in kolonlar:
                deger = satir.get(excel_baslik) if excel_baslik in df.columns else None
                if pd.isna(deger):
                    deger = None
                elif not isinstance(deger, str):
                    deger = str(deger)
                degerler.append(deger)
            con.execute(
                f'INSERT INTO "{tablo}" ({kolon_ifadesi}) VALUES ({yer_tutucular})',
                degerler,
            )
            yazilan += 1
        con.commit()
        return yazilan
    finally:
        con.close()
