from __future__ import annotations

"""Domain contract testleri (V20'den benimsendi + iki kez düzeltildi).

DÜZELTME TARİHÇESİ (üç aşama):
1) İlk incelemede services/family_balance.py "state_engine.py'ye hiç
   bağlı değil, kullanılmıyor" sanılmıştı.
2) Daha derin bir mimari taramada bu YANLIŞ çıktı: modül aslında
   src/excel_report.py::build_boxed_manager_excel üzerinden GERÇEKTEN
   canlıydı. Bu keşifle birlikte, ana unvanda 0 gerçek personel varken
   yardımcı kapasitesinin normu kapatmaması gerektiği (state_engine.py
   ile eşleştirme) "doğru davranış" kabul edilip family_balance.py buna
   göre düzeltilmişti.
3) SONRA kullanıcı, ürün mantığı açısından bu kararı yeniden
   değerlendirdi: KPI/norm dengeleme katmanının sorması gereken soru
   "aynı aile içindeki fiili kapasite normu karşılıyor mu?" olmalı —
   "bu kişinin unvanını değiştirelim" değil. 0 ana + N yardımcı, aile
   toplamı normu karşılıyorsa YAPAY 1 eksik + 1 fazla üretmek toplam
   rakamları ve transfer motorunu şişirir. Kullanıcının nihai kararı
   ("Kural A"): aile kapasitesi yeterliyse Eksik=0/Fazla=0, AYRICA "ana
   unvanda doğrudan görevli personel yok" bilgisini KAYBETMEDEN, ayrı
   bir niteliksel uyarı sütununda (_Ana Unvan Personelsiz /
   "Ana Unvan Personelsiz Uyarısı") korunur.

Bu, hem src/state_engine.py::_reconcile_main_family_rules hem
services/family_balance.py::balance_store_title_rows'da UYGULANMIŞTIR.
Aşağıdaki testler bu NİHAİ kararı doğrular.
"""

import pandas as pd


def test_note_about_future_resignation_does_not_deactivate_person():
    from services.personnel_status import row_is_active
    row = {"Açıklama": "15.08.2026 tarihinde istifa edecek", "İşten Çıkış": None}
    assert row_is_active(row) is True


def test_far_future_exit_date_keeps_person_active_until_date_arrives():
    """DÜZELTME (iş kuralı — kullanıcı ile netleştirildi, OMEHR
    hızlandırma şartnamesi Madde 13/76): önceden HERHANGİ bir çıkış
    tarihi (gelecekte olsa bile) kişiyi ANINDA pasif yapıyordu. Artık
    çıkış tarihi GELENE KADAR kişi aktif kalır."""
    from services.personnel_status import row_is_active
    import pandas as pd
    assert row_is_active({"İşten Çıkış": "2099-01-01"}) is True


def test_past_exit_date_deactivates_person():
    from services.personnel_status import row_is_active
    assert row_is_active({"İşten Çıkış": "2020-01-01"}) is False


def test_active_people_and_row_rule_are_identical():
    from services.personnel_status import active_people, row_is_active
    df = pd.DataFrame([
        {"İsim Soyisim": "Aktif", "İşten Çıkış": None},
        {"İsim Soyisim": "Çıkmış", "İşten Çıkış": "2026-08-09"},
        {"İsim Soyisim": "Notlu", "İşten Çıkış": None, "Açıklama": "istifa edecek"},
    ])
    expected = [row_is_active(r) for r in df.to_dict("records")]
    actual = df.index.isin(active_people(df).index).tolist()
    assert actual == expected


def test_kpi_contract_net_need_is_surplus_minus_deficit():
    from src.kpi_engine import kpis
    st = pd.DataFrame([{"Aktif Mevcut": 8, "Norm Kadro": 10, "Norm Eksiği": 3, "Norm Fazlası": 1}])
    result = kpis(st)
    assert result["Net İhtiyaç"] == -2


def test_no_exit_note_can_create_active_count_change():
    from services.personnel_status import active_people
    base = pd.DataFrame([{"İsim Soyisim": "A", "İşten Çıkış": None, "Açıklama": None}])
    noted = base.copy(); noted.loc[0, "Açıklama"] = "30.09.2026 ayrılabilir"
    assert len(active_people(base)) == len(active_people(noted)) == 1


def test_family_balance_applies_rule_a_with_qualitative_warning():
    """NİHAİ KARAR testi: 0 ana personel + aile toplamı normu karşılıyor
    → Eksik/Fazla dengelenir (Kural A) VE uyarı bayrağı True olur."""
    from services.family_balance import balance_store_title_rows
    frame = pd.DataFrame([
        {"Unvan": "MANAV", "Norm": 2, "Mevcut": 0, "Eksik": 2, "Fazla": 0},
        {"Unvan": "MANAV YARDIMCISI", "Norm": 0, "Mevcut": 2, "Eksik": 0, "Fazla": 0},
    ])
    out = balance_store_title_rows(
        frame, key_col="Unvan", norm_col="Norm", current_col="Mevcut",
        deficit_col="Eksik", surplus_col="Fazla",
    )
    eksik = int(out.loc[out["Unvan"] == "MANAV", "Eksik"].iloc[0])
    uyari = bool(out.loc[out["Unvan"] == "MANAV", "_Ana Unvan Personelsiz"].iloc[0])
    assert eksik == 0, f"Kural A: aile toplamı normu karşılıyorsa Eksik 0 olmalı, {eksik} bulundu."
    assert uyari is True, "0 ana personelle dengelendiğinde uyarı bayrağı True olmalı."


def test_family_balance_no_false_warning_when_main_has_minimum_staff():
    """Ana unvanda yeterli personel varken uyarı bayrağı yanlışlıkla
    True olmamalı."""
    from services.family_balance import balance_store_title_rows
    frame = pd.DataFrame([
        {"Unvan": "YÖNETİCİ", "Norm": 1, "Mevcut": 1, "Eksik": 0, "Fazla": 0},
        {"Unvan": "YÖNETİCİ YARDIMCISI", "Norm": 0, "Mevcut": 1, "Eksik": 0, "Fazla": 0},
    ])
    out = balance_store_title_rows(
        frame, key_col="Unvan", norm_col="Norm", current_col="Mevcut",
        deficit_col="Eksik", surplus_col="Fazla",
    )
    assert bool(out.loc[out["Unvan"] == "YÖNETİCİ", "_Ana Unvan Personelsiz"].iloc[0]) is False
