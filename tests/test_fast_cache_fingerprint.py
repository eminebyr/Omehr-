from __future__ import annotations

"""OMEHR Hızlandırma Şartnamesi Madde 6 — Excel Change Watcher regresyon testi.

Önceden dosya-seviyesi TEK mtime anahtarı kullanılıyordu: dosyanın
HERHANGİ bir sayfası değişince (ör. yalnız Fact_Mevcut), TÜM 64 sayfanın
önbelleği de "bayat" sayılıyordu. Bu test, steady-state'te (bir kişi
eklendikten sonra) YALNIZ gerçekten değişen sayfanın yeniden okunduğunu,
diğerlerinin AYNI DataFrame nesnesini koruduğunu doğrular.
"""

import shutil
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def gecici_input(tmp_path, isolated_root):
    hedef_dizin = tmp_path / "input"
    hedef_dizin.mkdir(exist_ok=True)
    kaynak = Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"
    hedef = hedef_dizin / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copyfile(kaynak, hedef)
    return hedef


def test_unrelated_sheets_are_not_reread_after_steady_state_write(gecici_input, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(gecici_input.parent.parent))
    from services.cached_excel_reader import read_sheet_cached, son_degisen_sayfalar, _SAYFA_ONBELLEGI
    from services.personnel_exit import load_personnel_view, add_personnel

    hedef = gecici_input
    # İlk yazma: bazı sayfalarda tek seferlik veri-temizliği normalizasyonu
    # olabilir (ör. sondaki boşluk kırpma) — bu YANILTICI olabileceğinden
    # steady-state'e ulaşmak için BİR kez ısındırma yazması yapılır.
    staff, magaza, unvan, _ = load_personnel_view(hedef)
    isinma = {c: None for c in staff.columns}
    isinma.update({"İsim Soyisim": "ISINMA", "Mağaza": magaza["Mağaza"].iloc[0],
        "MağazaID": magaza["MağazaID"].iloc[0], "Unvan": unvan["Unvan"].iloc[0],
        "UnvanID": unvan["UnvanID"].iloc[0], "İşe Giriş": "2026-08-01", "Departman": unvan["Unvan"].iloc[0]})
    add_personnel(input_path=hedef, root=gecici_input.parent.parent, staff=staff, yeni_kayit=isinma, username="test")
    read_sheet_cached(hedef, "Fact_Mevcut")
    read_sheet_cached(hedef, "Dim_Magaza")
    read_sheet_cached(hedef, "Mail_Listesi")

    durum = _SAYFA_ONBELLEGI[str(hedef.resolve())]
    id_once = {s: id(durum["sayfa_veri"][s]) for s in ("Dim_Magaza", "Mail_Listesi")}

    staff2, magaza2, unvan2, _ = load_personnel_view(hedef)
    yeni = {c: None for c in staff2.columns}
    yeni.update({"İsim Soyisim": "REGRESYON TEST", "Mağaza": magaza2["Mağaza"].iloc[0],
        "MağazaID": magaza2["MağazaID"].iloc[0], "Unvan": unvan2["Unvan"].iloc[0],
        "UnvanID": unvan2["UnvanID"].iloc[0], "İşe Giriş": "2026-08-10", "Departman": unvan2["Unvan"].iloc[0]})
    add_personnel(input_path=hedef, root=gecici_input.parent.parent, staff=staff2, yeni_kayit=yeni, username="test")

    read_sheet_cached(hedef, "Fact_Mevcut")
    degisenler = son_degisen_sayfalar(hedef)

    durum2 = _SAYFA_ONBELLEGI[str(hedef.resolve())]
    id_sonra = {s: id(durum2["sayfa_veri"][s]) for s in ("Dim_Magaza", "Mail_Listesi")}

    assert "Fact_Mevcut" in degisenler, "Fact_Mevcut değişikliği fingerprint'te görünmüyor."
    assert id_once["Dim_Magaza"] == id_sonra["Dim_Magaza"], (
        "REGRESYON: Dim_Magaza ilgisiz bir yazmadan sonra gereksiz yere yeniden okundu — "
        "sayfa fingerprint mekanizması bozulmuş olabilir."
    )
    assert id_once["Mail_Listesi"] == id_sonra["Mail_Listesi"], (
        "REGRESYON: Mail_Listesi ilgisiz bir yazmadan sonra gereksiz yere yeniden okundu."
    )
