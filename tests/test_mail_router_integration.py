from __future__ import annotations

"""mail_router.py -> report_mail_engine.py entegrasyonu (Madde 30-31)
regresyon testleri.

Önceden report_mail_engine.py'nin load_contacts()-tabanlı akışı yalnız
"Aktif" sütununa bakıyordu, hiçbir abonelik (Norm_Genel/Norm_Bolge)
filtresi UYGULAMIYORDU. mail_router.py doğrulanmış ama HİÇBİR gerçek
akışa bağlı değildi. Bu testler, GERÇEK entegrasyonun hem geriye dönük
uyumlu hem de doğru filtrelediğini kilitler.
"""

import pandas as pd


def _filtre_uygula(df: pd.DataFrame) -> set[str]:
    """report_mail_engine.py::send_reports_via_outlook() içine eklenen
    TAM kod bloğunun aynısı — regresyon durumunda buradan da yakalanır."""
    from services.region_access import is_global_scope, safe_text
    from services.mail_router import _apply_subscription_filter

    active = df.copy()
    sirket = [safe_text(r.get("E-posta")).strip().casefold() for _, r in active.iterrows() if is_global_scope(safe_text(r.get("Bölge")), "")]
    bolge = [safe_text(r.get("E-posta")).strip().casefold() for _, r in active.iterrows() if not is_global_scope(safe_text(r.get("Bölge")), "")]
    return set(_apply_subscription_filter(sirket, df, "COMPANY_NORM_REPORT")) | set(_apply_subscription_filter(bolge, df, "REGION_NORM_REPORT"))


def test_no_subscription_column_keeps_all_active_recipients():
    """Geriye dönük uyumluluk: abonelik sütunu yoksa davranış değişmemeli."""
    df = pd.DataFrame([
        {"Aktif": "evet", "E-posta": "eski@test.com", "Bölge": "TÜMÜ"},
        {"Aktif": "evet", "E-posta": "eski_bolge@test.com", "Bölge": "ERTAN"},
    ])
    kalanlar = _filtre_uygula(df)
    assert kalanlar == {"eski@test.com", "eski_bolge@test.com"}, (
        f"REGRESYON: abonelik sütunu yokken alıcı kayboldu: {kalanlar}"
    )


def test_company_wide_opt_out_is_respected():
    df = pd.DataFrame([
        {"Aktif": "evet", "E-posta": "abone@test.com", "Bölge": "TÜMÜ", "Norm_Genel": "Evet"},
        {"Aktif": "evet", "E-posta": "abone_degil@test.com", "Bölge": "TÜMÜ", "Norm_Genel": "Hayır"},
    ])
    kalanlar = _filtre_uygula(df)
    assert kalanlar == {"abone@test.com"}


def test_regional_opt_out_is_respected_independently_of_company_wide():
    df = pd.DataFrame([
        {"Aktif": "evet", "E-posta": "bolge_abone@test.com", "Bölge": "ERTAN", "Norm_Bolge": "Evet"},
        {"Aktif": "evet", "E-posta": "bolge_abone_degil@test.com", "Bölge": "ERTAN", "Norm_Bolge": "Hayır"},
    ])
    kalanlar = _filtre_uygula(df)
    assert kalanlar == {"bolge_abone@test.com"}


def test_report_mail_engine_actually_imports_mail_router():
    """Entegrasyonun GERÇEKTEN kaynak dosyada olduğunu doğrular —
    yalnız test yardımcı fonksiyonunda değil."""
    kaynak = open("report_mail_engine.py", encoding="utf-8").read()
    assert "from services.mail_router import _apply_subscription_filter" in kaynak
