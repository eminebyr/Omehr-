from __future__ import annotations

"""Mail Router (Madde 30-31) — regresyon testleri.

NOT: Bu modül şu an HİÇBİR gerçek gönderim akışına (worker.py, main.py,
personnel_notifications.py) BAĞLI DEĞİL — kendi başına doğru ve iyi
tasarlanmış, ama "kullanılmayan" durumda. Bunu bilinçli olarak bir
akışa BAĞLAMADIM (kullanıcı onayı gerektiren bir mimari genişletme
olur) — yalnız DOĞRU çalıştığını kilitliyorum.
"""

import pandas as pd


def test_company_report_falls_back_to_role_based_when_no_subscription_column():
    from services.mail_router import resolve_recipients
    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Rol": "ADMIN", "E-posta": "admin@test.com", "Aktif": "evet"},
    ])}
    alicilar = resolve_recipients(event_type="COMPANY_NORM_REPORT", scope="ALL", sheets=sheets)
    assert "admin@test.com" in alicilar


def test_region_report_does_not_leak_other_regions():
    from services.mail_router import resolve_recipients
    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Rol": "REGION", "Yetki Kapsamı": "ERTAN BÖLGESİ", "E-posta": "ertan@test.com", "Aktif": "evet"},
        {"Rol": "REGION", "Yetki Kapsamı": "CÜNEYT BÖLGESİ", "E-posta": "cuneyt@test.com", "Aktif": "evet"},
    ])}
    alicilar = resolve_recipients(event_type="REGION_NORM_REPORT", scope="ERTAN BÖLGESİ", sheets=sheets)
    assert "ertan@test.com" in alicilar
    assert "cuneyt@test.com" not in alicilar, "REGRESYON (Madde 25): başka bölge sızıyor."


def test_subscription_opt_out_actually_removes_recipient():
    from services.mail_router import resolve_recipients
    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Rol": "ADMIN", "E-posta": "abone@test.com", "Aktif": "evet", "Norm_Genel": "Evet"},
        {"Rol": "ADMIN", "E-posta": "abone_degil@test.com", "Aktif": "evet", "Norm_Genel": "Hayır"},
    ])}
    alicilar = resolve_recipients(event_type="COMPANY_NORM_REPORT", scope="ALL", sheets=sheets)
    assert "abone@test.com" in alicilar
    assert "abone_degil@test.com" not in alicilar
