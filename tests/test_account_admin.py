from __future__ import annotations

import pandas as pd


def test_named_admin_hr_director_becomes_admin_when_admin_role_is_missing():
    from web.accounts import accounts

    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Web Kullanıcı": "ik1", "Rol": "HR_DIRECTOR", "Yetki Kapsamı": "ALL", "Onay Seviyesi": 2, "Aktif": "Evet"},
        {"Web Kullanıcı": "admin", "Rol": "HR_DIRECTOR", "Yetki Kapsamı": "ALL", "Onay Seviyesi": 2, "Aktif": "Evet"},
        {"Web Kullanıcı": "bolge_01", "Rol": "REGION", "Yetki Kapsamı": "BOLGE 1", "Onay Seviyesi": 1, "Aktif": "Evet"},
    ])}

    result = accounts(sheets)

    assert result.loc[result["Web Kullanıcı"].eq("admin"), "Rol"].item() == "ADMIN"
    assert result.loc[result["Web Kullanıcı"].eq("ik1"), "Rol"].item() == "HR_DIRECTOR"


def test_existing_admin_is_preserved_and_no_other_user_is_promoted():
    from web.accounts import accounts

    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Web Kullanıcı": "yonetici", "Rol": "ADMIN", "Yetki Kapsamı": "ALL", "Onay Seviyesi": 2, "Aktif": "Evet"},
        {"Web Kullanıcı": "ik", "Rol": "HR_DIRECTOR", "Yetki Kapsamı": "ALL", "Onay Seviyesi": 2, "Aktif": "Evet"},
    ])}

    result = accounts(sheets)

    assert result.set_index("Web Kullanıcı").loc["yonetici", "Rol"] == "ADMIN"
    assert result.set_index("Web Kullanıcı").loc["ik", "Rol"] == "HR_DIRECTOR"


def test_only_admin_can_manage_other_user_passwords():
    from web.accounts import can_manage_user_passwords

    assert can_manage_user_passwords("ADMIN") is True
    assert can_manage_user_passwords("HR_DIRECTOR") is False
    assert can_manage_user_passwords("REGION") is False


def test_inactive_accounts_are_not_available_for_password_reset():
    from web.accounts import accounts, password_reset_usernames

    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Web Kullanıcı": "aktif", "Rol": "ADMIN", "Yetki Kapsamı": "ALL", "Onay Seviyesi": 2, "Aktif": "Evet"},
        {"Web Kullanıcı": "pasif", "Rol": "REGION", "Yetki Kapsamı": "BOLGE", "Onay Seviyesi": 1, "Aktif": "Hayır"},
    ])}

    active_accounts = accounts(sheets)
    assert active_accounts["Web Kullanıcı"].tolist() == ["aktif"]
    assert password_reset_usernames(active_accounts, "aktif") == []


def test_password_reset_list_contains_other_active_users_but_not_current_admin():
    from web.accounts import accounts, password_reset_labels, password_reset_usernames

    sheets = {"Mail_Listesi": pd.DataFrame([
        {"Web Kullanıcı": "admin", "Sorumlu": "İnsan Kaynakları Direktörlüğü", "Rol": "HR_DIRECTOR", "Yetki Kapsamı": "ALL", "Onay Seviyesi": 2, "Aktif": "Evet"},
        {"Web Kullanıcı": "ertan", "Sorumlu": "ERTAN TEKİ", "Rol": "REGION", "Yetki Kapsamı": "ERTAN TEKİ", "Onay Seviyesi": 1, "Aktif": "Evet"},
        {"Web Kullanıcı": "derya", "Sorumlu": "DERYA YARDIMCI", "Rol": "REGION", "Yetki Kapsamı": "DERYA YARDIMCI", "Onay Seviyesi": 1, "Aktif": "Evet"},
    ])}

    active_accounts = accounts(sheets)

    assert password_reset_usernames(active_accounts, "admin") == ["derya", "ertan"]
    labels = password_reset_labels(active_accounts)
    assert labels["ertan"] == "ERTAN TEKİ (ertan) · REGION"


def test_admin_reset_unlocks_account_and_new_temporary_password_can_log_in(tmp_path, monkeypatch):
    monkeypatch.setenv("OMEHR_RUNTIME_ROOT", str(tmp_path))
    from services.security import authenticate, set_password
    from web.accounts import reset_user_password

    tenant = "OMEHR"
    set_password("ertan", "IlkSifre2026", tenant_id=tenant)
    for _ in range(5):
        authenticate("ertan", "YanlisSifre2026", tenant_id=tenant)
    locked, _, _ = authenticate("ertan", "IlkSifre2026", tenant_id=tenant)
    assert locked is False

    reset_user_password("ertan", "YeniSifre2027", tenant_id=tenant)
    ok, message, must_change = authenticate("ertan", "YeniSifre2027", tenant_id=tenant)

    assert ok is True
    assert message == ""
    assert must_change is True
