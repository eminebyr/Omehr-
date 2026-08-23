"""services/security.py — çok kiracılı kimlik doğrulama testleri.

Bu modülün önceden HİÇ özel testi yoktu. Kritik bir değişiklik (credentials
tablosuna tenant_id eklenmesi, eski şemadan güvenli göç, kiracı durumu
kontrolü) yapıldığı için gerçek testler burada yazıldı.
"""
from __future__ import annotations

import sqlite3

import pytest


def test_iki_farkli_kiracida_ayni_kullanici_adi_carpismaz(isolated_root, monkeypatch):
    """KRİTİK: iki farklı firma aynı kullanıcı adını (ör. 'ik1') kullanırsa
    şifreleri birbirine karışmamalı — eski şemada (username-only PK) bu
    çakışırdı."""
    from services import security
    import importlib
    importlib.reload(security)

    security.set_password("ik1", "SifreA123456", tenant_id="FIRMA_A")
    security.set_password("ik1", "SifreB999999", tenant_id="FIRMA_B")

    ok_a, _, _ = security.authenticate("ik1", "SifreA123456", tenant_id="FIRMA_A")
    ok_b, _, _ = security.authenticate("ik1", "SifreB999999", tenant_id="FIRMA_B")
    assert ok_a is True
    assert ok_b is True

    # FIRMA_A'nın şifresiyle FIRMA_B'ye giriş denemesi BAŞARISIZ olmalı.
    capraz, _, _ = security.authenticate("ik1", "SifreA123456", tenant_id="FIRMA_B")
    assert capraz is False


def test_eski_semadan_guvenli_goc(isolated_root, monkeypatch):
    """Eski (V19.21.28 öncesi, tenant_id'siz) bir credentials tablosu
    varsa, yeni şemaya geçerken mevcut şifreler KAYBOLMAMALI ve
    varsayılan 'OMEHR' kiracısına atanmalı."""
    from services import security
    import importlib
    importlib.reload(security)

    security._db_path().parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(security._db_path())
    con.executescript(
        """
        DROP TABLE IF EXISTS credentials;
        CREATE TABLE credentials(
            username TEXT PRIMARY KEY, salt BLOB NOT NULL, password_hash BLOB NOT NULL,
            iterations INTEGER NOT NULL, must_change INTEGER NOT NULL DEFAULT 1,
            failed_attempts INTEGER NOT NULL DEFAULT 0, locked_until TEXT, changed_at TEXT NOT NULL
        );
        """
    )
    salt = b"0123456789ABCDEF"
    digest = security._derive("EskiSifre123456", salt)
    con.execute(
        "INSERT INTO credentials VALUES('eskikullanici',?,?,?,0,0,NULL,'2026-01-01T00:00:00')",
        (salt, digest, security.ITERATIONS),
    )
    con.commit()
    con.close()

    ok, msg, _ = security.authenticate("eskikullanici", "EskiSifre123456", tenant_id="OMEHR")
    assert ok is True, msg


def test_askidaki_kiraci_dogru_sifreyle_bile_giremez(isolated_root, monkeypatch):
    from services import security
    from services import tenant_registry
    import importlib
    importlib.reload(security)
    importlib.reload(tenant_registry)

    tenant_registry.create_tenant("ASKIDAKI", "Askıdaki Firma A.Ş.")
    tenant_registry.set_status("ASKIDAKI", "askida")
    security.set_password("kullanici1", "DogruSifre123456", tenant_id="ASKIDAKI")

    ok, msg, _ = security.authenticate("kullanici1", "DogruSifre123456", tenant_id="ASKIDAKI")
    assert ok is False
    assert "askı" in msg.lower() or "kapat" in msg.lower()


def test_hic_kayitli_olmayan_kiraci_engellenmez(isolated_root, monkeypatch):
    """DÜZELTME DOĞRULAMASI: tenants tablosunda HİÇ kaydı olmayan bir
    kiracı (eski/tek-kiracılı kurulumlarda normal durum), 'askıda'
    sayılıp yanlışlıkla engellenmemeli — yalnız AÇIKÇA askıda/iptal
    olarak KAYITLI kiracılar engellenir."""
    from services import security
    import importlib
    importlib.reload(security)

    security.set_password("tekkullanici", "Sifre123456A", tenant_id="HICKAYITSIZ")
    ok, msg, _ = security.authenticate("tekkullanici", "Sifre123456A", tenant_id="HICKAYITSIZ")
    assert ok is True, msg


def test_yanlis_sifre_hala_reddedilir(isolated_root, monkeypatch):
    from services import security
    import importlib
    importlib.reload(security)

    security.set_password("normal", "DogruSifre1234", tenant_id="OMEHR")
    ok, msg, _ = security.authenticate("normal", "YanlisSifre999", tenant_id="OMEHR")
    assert ok is False
    assert "hatalı" in msg.lower()
