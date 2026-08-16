from __future__ import annotations

"""Madde 11 — İşe Giriş servis katmanı doğrulaması (regresyon testleri).

Önceden add_personnel() hiçbir doğrulama yapmıyordu; bu kontroller
yalnız UI'daki selectbox'larla dolaylı sağlanıyordu. Servis katmanının
kendisi artık mağaza/unvan geçerliliğini ve mükerrer aktif personeli
kontrol ediyor.
"""

import shutil
import pytest


@pytest.fixture
def _hazirlanmis_dizin(tmp_path):
    (tmp_path / "input").mkdir()
    shutil.copyfile(
        "ORNEK_TEST_VERISI/BASDAS_AI_NORM_TRANSFER_INPUT.xlsx",
        tmp_path / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx",
    )
    return tmp_path


def test_add_personnel_rejects_unknown_store(_hazirlanmis_dizin):
    from services.personnel_exit import load_personnel_view, add_personnel
    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    with pytest.raises(ValueError, match="Mağaza"):
        add_personnel(input_path=hedef, root=_hazirlanmis_dizin, staff=staff, yeni_kayit={
            "İsim Soyisim": "TEST", "MağazaID": "YOK_BOYLE_BIR_MAGAZA",
            "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-11",
        }, username="test")


def test_add_personnel_rejects_unknown_title(_hazirlanmis_dizin):
    from services.personnel_exit import load_personnel_view, add_personnel
    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    with pytest.raises(ValueError, match="Unvan"):
        add_personnel(input_path=hedef, root=_hazirlanmis_dizin, staff=staff, yeni_kayit={
            "İsim Soyisim": "TEST", "MağazaID": magaza["MağazaID"].iloc[0],
            "UnvanID": "YOK_BOYLE_BIR_UNVAN", "İşe Giriş": "2026-08-11",
        }, username="test")


def test_add_personnel_rejects_empty_name(_hazirlanmis_dizin):
    from services.personnel_exit import load_personnel_view, add_personnel
    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    with pytest.raises(ValueError, match="İsim"):
        add_personnel(input_path=hedef, root=_hazirlanmis_dizin, staff=staff, yeni_kayit={
            "İsim Soyisim": "", "MağazaID": magaza["MağazaID"].iloc[0],
            "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-11",
        }, username="test")


def test_add_personnel_rejects_duplicate_active_person(_hazirlanmis_dizin):
    from services.personnel_exit import load_personnel_view, add_personnel
    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    mevcut = staff[staff["İşten Çıkış"].isna()].iloc[0]
    with pytest.raises(ValueError, match="AKTİF"):
        add_personnel(input_path=hedef, root=_hazirlanmis_dizin, staff=staff, yeni_kayit={
            "İsim Soyisim": mevcut["İsim Soyisim"], "MağazaID": magaza["MağazaID"].iloc[0],
            "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-11",
        }, username="test")


def test_add_personnel_accepts_valid_entry(_hazirlanmis_dizin):
    from services.personnel_exit import load_personnel_view, add_personnel
    hedef = _hazirlanmis_dizin / "input" / "BASDAS_AI_NORM_TRANSFER_INPUT.xlsx"
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    add_personnel(input_path=hedef, root=_hazirlanmis_dizin, staff=staff, yeni_kayit={
        "İsim Soyisim": "GEÇERLİ TEST KİŞİ", "MağazaID": magaza["MağazaID"].iloc[0],
        "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-11", "Departman": unvan["Unvan"].iloc[0],
    }, username="test")
    staff2, *_ = load_personnel_view(hedef)
    assert (staff2["İsim Soyisim"] == "GEÇERLİ TEST KİŞİ").any()
