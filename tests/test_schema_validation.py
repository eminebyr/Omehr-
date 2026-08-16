"""services.schema_validation testleri.

Bu modül main.py'nin İLK adımıdır: zorunlu bir sütun eksikse pipeline
DURMALI (SchemaValidationError), veri kalitesi sorunlarında ise UYARI
vermeli ama akış BOZULMAMALI. İki davranış da burada doğrulanıyor.
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.schema_validation import SchemaValidationError, validate


def _valid_sheets():
    return {
        "Fact_Mevcut": pd.DataFrame([
            {"PersonelID": "P1", "MağazaID": 1, "UnvanID": "U1", "İsim Soyisim": "Kişi 1", "İşten Çıkış": None},
            {"PersonelID": "P2", "MağazaID": 1, "UnvanID": "U1", "İsim Soyisim": "Kişi 2", "İşten Çıkış": None},
        ]),
        "Fact_Norm": pd.DataFrame([
            {"MağazaID": 1, "UnvanID": "U1", "Norm Kadro": 3},
        ]),
        "Dim_Magaza": pd.DataFrame([{"MağazaID": 1, "Mağaza": "A Mağazası"}]),
        "Dim_Unvan": pd.DataFrame([{"UnvanID": "U1", "Unvan": "KASİYER"}]),
    }


def test_valid_minimal_sheets_pass_without_critical_errors():
    sonuc = validate(_valid_sheets())
    assert sonuc.kritik_hatalar == []


def test_missing_required_sheet_raises_schema_validation_error():
    sheets = _valid_sheets()
    del sheets["Fact_Norm"]
    with pytest.raises(SchemaValidationError):
        validate(sheets)


def test_missing_required_column_raises_schema_validation_error():
    sheets = _valid_sheets()
    sheets["Fact_Mevcut"] = sheets["Fact_Mevcut"].drop(columns=["İsim Soyisim"])
    with pytest.raises(SchemaValidationError):
        validate(sheets)


def test_empty_required_sheet_raises_schema_validation_error():
    sheets = _valid_sheets()
    sheets["Dim_Magaza"] = pd.DataFrame()
    with pytest.raises(SchemaValidationError):
        validate(sheets)


def test_duplicate_active_personel_id_is_a_warning_not_a_crash():
    """Yinelenen PersonelID bir VERİ KALİTESİ sorunudur (loglanır) ama
    pipeline'ı DURDURMAMALI — main.py'nin devam edebilmesi gerekir."""
    sheets = _valid_sheets()
    sheets["Fact_Mevcut"] = pd.concat(
        [sheets["Fact_Mevcut"], sheets["Fact_Mevcut"].iloc[[0]]], ignore_index=True
    )
    sonuc = validate(sheets)  # exception fırlatmamalı
    assert not sonuc.sorunsuz
    assert any("İsim Soyisim" in uyari for uyari in sonuc.uyarilar)
