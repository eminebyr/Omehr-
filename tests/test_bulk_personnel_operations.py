"""Toplu işe giriş / toplu işten çıkış — gerçek fonksiyonel testler.

FAST V9 entegrasyonuyla eklenen add_personnel_bulk/process_exits_bulk
fonksiyonlarını GERÇEK veriyle uçtan uca doğrular: tek yazma işlemi,
kişi başına farklı çıkış kodu/nedeni, kod/neden grup uyuşmazlığının
servis katmanında reddedildiği, zaten çıkmış birinin tekrar işlenemediği.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd
import pytest

from services.personnel_exit import (
    load_personnel_view, add_personnel_bulk, process_exits_bulk,
)
from src.data_loading import load
from src.state_engine import state
from src.kpi_engine import kpis


@pytest.fixture
def gercek_veri_kok(tmp_path):
    kaynak = Path(__file__).resolve().parents[1] / "ORNEK_TEST_VERISI" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"
    (tmp_path / "input").mkdir()
    hedef = tmp_path / "input" / "OMEHR_AI_NORM_TRANSFER_INPUT.xlsx"
    shutil.copyfile(kaynak, hedef)
    (tmp_path / "output").mkdir()
    (tmp_path / "backup").mkdir()
    return tmp_path, hedef


def _baseline_kpi(input_path):
    sheets = pd.read_excel(input_path, sheet_name=None, dtype=object)
    stores, _ = state(sheets["Fact_Norm"], sheets["Fact_Mevcut"], sheets)
    return kpis(stores)


def test_add_personnel_bulk_adds_all_records_in_one_write(gercek_veri_kok):
    root, input_path = gercek_veri_kok
    once = _baseline_kpi(input_path)

    staff, magaza, unvan, _ = load_personnel_view(input_path)
    magaza_id, magaza_ad = magaza["MağazaID"].iloc[0], magaza["Mağaza"].iloc[0]
    unvan_id, unvan_ad = unvan["UnvanID"].iloc[0], unvan["Unvan"].iloc[0]

    yeni_kayitlar = [
        {c: None for c in staff.columns} | {
            "İsim Soyisim": f"TOPLU TEST KİŞİ {i}", "Mağaza": magaza_ad, "MağazaID": magaza_id,
            "Unvan": unvan_ad, "UnvanID": unvan_id, "Departman": unvan_ad,
            "İşe Giriş": "2026-08-09", "İşten Çıkış": None,
        }
        for i in range(3)
    ]
    sonuc = add_personnel_bulk(input_path=input_path, root=root, staff=staff, yeni_kayitlar=yeni_kayitlar, username="test")
    assert sonuc["eklenen"] == 3

    sonra = _baseline_kpi(input_path)
    assert sonra["Aktif Mevcut"] == once["Aktif Mevcut"] + 3


def test_process_exits_bulk_each_person_keeps_own_code_and_reason(gercek_veri_kok):
    root, input_path = gercek_veri_kok
    staff, _, _, cikis_nedeni = load_personnel_view(input_path)
    aktif = staff[staff["İşten Çıkış"].isna()].head(2)
    assert len(aktif) == 2, "test için en az 2 aktif personel gerekli"

    idx1, idx2 = aktif.index[0], aktif.index[1]
    neden1 = cikis_nedeni.iloc[0]
    # farklı gruptan bir neden bul (varsa) — kişi başına FARKLI kod/neden test edilsin
    diger_gruplar = cikis_nedeni[cikis_nedeni["CikisGrubu"] != neden1["CikisGrubu"]]
    neden2 = diger_gruplar.iloc[0] if not diger_gruplar.empty else cikis_nedeni.iloc[1]

    exits = [
        {"index": idx1, "cikis_tarihi": "2026-08-09", "cikis_kodu": str(neden1["CikisGrubu"]),
         "cikis_nedeni_id": neden1["CikisNedeniID"], "cikis_nedeni_metni": str(neden1["CikisNedeni"])},
        {"index": idx2, "cikis_tarihi": "2026-08-09", "cikis_kodu": str(neden2["CikisGrubu"]),
         "cikis_nedeni_id": neden2["CikisNedeniID"], "cikis_nedeni_metni": str(neden2["CikisNedeni"])},
    ]
    sonuc = process_exits_bulk(input_path=input_path, root=root, cikislar=exits, kullanici="test")
    assert sonuc["guncellenen_satir"] == 2

    guncel, *_ = load_personnel_view(input_path)
    assert int(guncel.loc[idx1, "CikisNedeniID"]) == int(neden1["CikisNedeniID"])
    assert int(guncel.loc[idx2, "CikisNedeniID"]) == int(neden2["CikisNedeniID"])
    assert guncel.loc[idx1, "İşten Çıkış"] is not None


def test_process_exits_bulk_rejects_mismatched_code_and_reason_group(gercek_veri_kok):
    """DÜZELTME (Madde 15 — her satır bağımsız): kod/neden grup uyuşmazlığı
    artık TÜM toplu işlemi reddetmez — yalnız o SATIR başarısız sayılır,
    sonuçta ayrı raporlanır (istisna fırlatılmaz)."""
    root, input_path = gercek_veri_kok
    staff, _, _, cikis_nedeni = load_personnel_view(input_path)
    aktif_idx = staff[staff["İşten Çıkış"].isna()].index[0]
    neden = cikis_nedeni.iloc[0]

    yanlis_kod = "GEÇERSİZ_GRUP_" + str(neden["CikisGrubu"])
    exits = [{
        "index": aktif_idx, "cikis_tarihi": "2026-08-09", "cikis_kodu": yanlis_kod,
        "cikis_nedeni_id": neden["CikisNedeniID"], "cikis_nedeni_metni": str(neden["CikisNedeni"]),
    }]
    sonuc = process_exits_bulk(input_path=input_path, root=root, cikislar=exits, kullanici="test")
    assert sonuc["guncellenen_satir"] == 0
    assert sonuc["basarisiz_satir"] == 1
    assert "uyumsuz" in sonuc["hatalar"][0]["hata"]

    # reddedilen satırdan sonra veri DEĞİŞMEMİŞ olmalı
    guncel, *_ = load_personnel_view(input_path)
    assert guncel.loc[aktif_idx, "İşten Çıkış"] is None or pd.isna(guncel.loc[aktif_idx, "İşten Çıkış"])


def test_process_exits_bulk_rejects_already_exited_person(gercek_veri_kok):
    """DÜZELTME (Madde 15): zaten çıkmış personel için 2. deneme artık
    istisna fırlatmaz — o satır başarısız sayılıp ayrı raporlanır."""
    root, input_path = gercek_veri_kok
    staff, _, _, cikis_nedeni = load_personnel_view(input_path)
    idx = staff[staff["İşten Çıkış"].isna()].index[0]
    neden = cikis_nedeni.iloc[0]
    exits = [{
        "index": idx, "cikis_tarihi": "2026-08-09", "cikis_kodu": str(neden["CikisGrubu"]),
        "cikis_nedeni_id": neden["CikisNedeniID"], "cikis_nedeni_metni": str(neden["CikisNedeni"]),
    }]
    process_exits_bulk(input_path=input_path, root=root, cikislar=exits, kullanici="test")

    sonuc2 = process_exits_bulk(input_path=input_path, root=root, cikislar=exits, kullanici="test")
    assert sonuc2["guncellenen_satir"] == 0
    assert sonuc2["basarisiz_satir"] == 1
    assert "zaten kayıtlı" in sonuc2["hatalar"][0]["hata"]


def test_no_hardcoded_personal_or_company_email_in_shared_code():
    """DÜZELTME (çok kiracılı SaaS): entegrasyon sırasında bulunan,
    paylaşılan koda gömülü sabit kişi/firma bilgilerinin GERÇEKTEN
    kaldırıldığını doğrular — regresyon koruması."""
    kod_kok = Path(__file__).resolve().parents[1]
    kontrol_edilecek = [
        "services/personnel_notifications.py", "services/message_personalization.py",
        "services/management_center.py", "web/accounts.py", "web/app.py",
        "services/puantaj_hatirlatma.py",
    ]
    yasakli = ["omer.arasin@basdasmarket.com", '"M. Feyzi Başdaş"', "ikd@basdasmarket.com\""]
    for dosya in kontrol_edilecek:
        icerik = (kod_kok / dosya).read_text(encoding="utf-8")
        for kod_disinda_metin in ["NOTIFY_TO = [\"ika", "APPROVERS = {\"insan"]:
            assert kod_disinda_metin not in icerik, f"{dosya}: sabit kodlanmış liste geri gelmiş"
