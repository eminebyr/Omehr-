from __future__ import annotations

import pytest


def test_account_locks_after_max_failed_attempts(isolated_root):
    from services.security import set_password, authenticate, MAX_FAILURES

    set_password("kaba_kuvvet_test", "DogruSifre123!", tenant_id="TESTFIRMA")

    for _ in range(MAX_FAILURES):
        ok, _, _ = authenticate("kaba_kuvvet_test", "YanlisSifre", tenant_id="TESTFIRMA")
        assert ok is False

    # Kilitlendikten sonra DOĞRU şifre bile reddedilmeli.
    ok, msg, _ = authenticate("kaba_kuvvet_test", "DogruSifre123!", tenant_id="TESTFIRMA")
    assert ok is False
    assert "kilitli" in msg.casefold()


def test_successful_login_resets_failed_attempt_counter(isolated_root):
    from services.security import set_password, authenticate, MAX_FAILURES

    set_password("sayac_sifirlama_test", "DogruSifre123!", tenant_id="TESTFIRMA")

    for _ in range(MAX_FAILURES - 1):
        authenticate("sayac_sifirlama_test", "YanlisSifre", tenant_id="TESTFIRMA")

    # Kilitlenmeden ÖNCE (son deneme kalmışken) doğru şifreyle giriş sayacı sıfırlamalı.
    ok, _, _ = authenticate("sayac_sifirlama_test", "DogruSifre123!", tenant_id="TESTFIRMA")
    assert ok is True

    # Sıfırlandığı için tekrar MAX_FAILURES-1 kadar yanlış deneme YETMEMELİ.
    for _ in range(MAX_FAILURES - 1):
        authenticate("sayac_sifirlama_test", "YanlisSifre", tenant_id="TESTFIRMA")
    ok, msg, _ = authenticate("sayac_sifirlama_test", "DogruSifre123!", tenant_id="TESTFIRMA")
    assert ok is True, f"Sayaç sıfırlanmamış görünüyor: {msg}"


def test_password_policy_rejects_weak_passwords():
    from services.security import password_error
    assert password_error("kisa1A") != ""
    assert password_error("tumkucukharf1") != ""
    assert password_error("TUMBUYUKHARF1") != ""
    assert password_error("HicRakamYok") != ""
    assert password_error("GuvenliSifre123") == ""
