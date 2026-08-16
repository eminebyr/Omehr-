"""EXCEL -> VERİTABANI GÖÇ ARACI (tek seferlik/tekrarlanabilir).

input/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx dosyasındaki 62+ sayfayı okuyup
services/input_db_schema.py'nin tanımladığı tablolara aktarır. Idempotent'tir
(tekrar çalıştırılırsa tabloları TEMİZLEYİP yeniden doldurur — Excel HER
ZAMAN "doğru" kaynak kabul edilir bu geçiş anında).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.input_db_schema import load_schema
from services.input_data_access import ensure_schema, write_sheet, _sqlite_path


def migrate_excel_to_db(excel_path: str, kullanici: str = "GOC_ARACI", tenant_id: str | None = None) -> dict[str, dict]:
    ensure_schema()
    sema = load_schema()
    sonuclar = {}
    # DÜZELTME (performans): önceden header_row==2 olan HER sayfa için
    # dosyanın TAMAMI yeniden açılıp okunuyordu (~0.5 sn/sayfa, 26 sayfa
    # ~6 sn) — ölçüldü: TEK açık ExcelFile handle'ı üzerinden okumak bu
    # süreyi ~2,6x düşürüyor (göç toplamda ~10 sn'den ~5 sn'ye indi).
    with pd.ExcelFile(excel_path) as xls:
        sheets = {s: pd.read_excel(xls, sheet_name=s, dtype=object) for s in xls.sheet_names}
        for sheet_adi, bilgi in sema.items():
            df = sheets.get(sheet_adi)
            header_row = bilgi["header_row"]
            if df is None:
                sonuclar[sheet_adi] = {"durum": "EXCEL'DE YOK", "satir": 0}
                continue
            if header_row == 2:
                # gerçek başlıklar 2. satırda (ör. Fazla Mesai gibi başlık
                # şeridi taşıyan sayfalar) — AYNI açık handle üzerinden
                # header=1 ile yeniden oku (dosyayı YENİDEN AÇMADAN).
                df = pd.read_excel(xls, sheet_name=sheet_adi, header=1, dtype=object)
            yazilan = write_sheet(sheet_adi, df, kullanici=kullanici, tenant_id=tenant_id)
            sonuclar[sheet_adi] = {"durum": "OK", "satir": yazilan}
    return sonuclar


if __name__ == "__main__":
    yol = sys.argv[1] if len(sys.argv) > 1 else "input/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    kiraci = sys.argv[2] if len(sys.argv) > 2 else None
    sonuc = migrate_excel_to_db(yol, tenant_id=kiraci)
    toplam = sum(v["satir"] for v in sonuc.values())
    basarisiz = [k for k, v in sonuc.items() if v["durum"] != "OK"]
    print(f"Göç tamamlandı: {len(sonuc)} sayfa, {toplam} satır.")
    if basarisiz:
        print("EXCEL'DE BULUNAMAYAN SAYFALAR:", basarisiz)
