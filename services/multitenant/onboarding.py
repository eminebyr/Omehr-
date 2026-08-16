"""KENDİ KENDİNE KAYIT (self-service onboarding) — çekirdek mantık.

"Kurulum.bat çalıştır" yerine web üzerinden: yeni firma kaydı → ilk admin
hesabı → (isteğe bağlı) mevcut Excel'in içe aktarımı. Streamlit'e bağımlı
değildir — web/app.py bu fonksiyonları çağırıp arayüzü çizer, böylece
mantık ayrı test edilebilir.

Üç adım birbirinden BAĞIMSIZ hatalarla başarısız olabilir (ör. tenant_id
zaten alınmış, şifre çok zayıf) — her adım kendi net hata mesajını döner,
önceki adımların geri alınması GEREKMEZ (tenant kaydı ile admin hesabı
ayrı, idempotent adımlardır; aynı tenant_id ile tekrar admin oluşturma
denemesi de güvenlidir çünkü set_password zaten var olan kullanıcıyı
GÜNCELLER, çoğaltmaz).
"""
from __future__ import annotations

import re

from services.multitenant import tenant_registry
from services import security


_TENANT_ID_DESENI = re.compile(r"^[A-Z][A-Z0-9_]{2,19}$")
_MIN_SIFRE_UZUNLUK = 10


def validate_tenant_id(tenant_id: str) -> tuple[bool, str]:
    tenant_id = (tenant_id or "").strip().upper()
    if not _TENANT_ID_DESENI.match(tenant_id):
        return False, (
            "Firma kodu 3-20 karakter olmalı, harfle başlamalı, yalnız "
            "büyük harf/rakam/alt çizgi içerebilir (ör. AKMEMARKET)."
        )
    if tenant_registry.get_tenant(tenant_id) is not None:
        return False, f"'{tenant_id}' kodu zaten kullanılıyor — başka bir kod seçin."
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    if len(password or "") < _MIN_SIFRE_UZUNLUK:
        return False, f"Şifre en az {_MIN_SIFRE_UZUNLUK} karakter olmalı."
    if password.strip().lower() in {"12345678901234", "password123", "sifre123456"}:
        return False, "Bu şifre çok yaygın — daha güçlü bir şifre seçin."
    return True, ""


def register_tenant(tenant_id: str, firma_adi: str, plan: str = "deneme") -> dict:
    """1. adım: firma kaydı. Zaten alınmış kod veya geçersiz plan durumunda
    ValueError fırlatır (tenant_registry.create_tenant'ın davranışı).

    DÜZELTME (bizzat gerçek bir uçtan uca testle bulundu): önceden yalnız
    'plan' ismi create_tenant()'a geçiriliyordu, kota DEĞERLERİ değil —
    bu yüzden create_tenant()'ın VARSAYILAN kotası (10 şube/5 kullanıcı)
    HER PLAN için kullanılıyordu; 'standart' veya 'kurumsal' seçmenin
    kota açısından hiçbir etkisi yoktu. Artık services.multitenant.billing.
    PLAN_KOTALARI'ndan doğru kota değerleri alınıp geçiriliyor."""
    tenant_id = tenant_id.strip().upper()
    ok, hata = validate_tenant_id(tenant_id)
    if not ok:
        raise ValueError(hata)
    if not firma_adi.strip():
        raise ValueError("Firma adı boş olamaz.")
    from services.multitenant.billing import PLAN_KOTALARI
    kotalar = PLAN_KOTALARI.get(plan, {"sube_kotasi": 10, "kullanici_kotasi": 5})
    return tenant_registry.create_tenant(
        tenant_id, firma_adi.strip(), plan=plan,
        sube_kotasi=kotalar["sube_kotasi"], kullanici_kotasi=kotalar["kullanici_kotasi"],
    )


def register_first_admin(tenant_id: str, username: str, password: str, e_posta: str = "") -> dict:
    """2. adım: ilk yönetici hesabı. must_change=False — kayıt sırasında
    kendi belirlediği şifreyi tekrar değiştirmesi istenmez (ilk giriş
    zorunlu şifre değişimi yalnız İK'nın SONRADAN oluşturduğu geçici
    şifreler için anlamlıdır, bkz. services/security.py).

    NOT: yalnız services.security'ye şifre yazmak YETMEZ — giriş akışı
    (web/app.py) kullanıcıyı Mail_Listesi sayfasındaki 'Web Kullanıcı'
    satırından bulur (yetki/rol/e-posta buradan okunur). Bu yüzden
    burada AYRICA tenant'ın Mail_Listesi'ne bir ADMIN satırı yazılır —
    aksi halde doğru şifreyle bile giriş başarısız olurdu (kullanıcı
    dizininde eşleşme bulunamaz)."""
    tenant_id = tenant_id.strip().upper()
    username = username.strip()
    if not username:
        raise ValueError("Kullanıcı adı boş olamaz.")
    ok, hata = validate_password(password)
    if not ok:
        raise ValueError(hata)
    if tenant_registry.get_tenant(tenant_id) is None:
        raise ValueError(f"'{tenant_id}' kodlu bir firma kaydı bulunamadı — önce 1. adımı tamamlayın.")
    security.set_password(username, password, must_change=False, tenant_id=tenant_id)

    from services.input_data_access import ensure_schema, read_sheet, write_sheet
    import pandas as pd
    ensure_schema()
    mevcut = read_sheet("Mail_Listesi", tenant_id=tenant_id)
    zaten_var = not mevcut.empty and (mevcut["Web Kullanıcı"].astype(str).str.strip() == username).any()
    if not zaten_var:
        yeni_satir = {c: None for c in mevcut.columns} if not mevcut.empty else {
            "Bölge": "", "Sorumlu": username, "E-posta": e_posta.strip(), "Aktif": "Evet",
            "Gönderim Tipi": "", "PDF Ekle": "", "Excel Ekle": "", "Açıklama": "İlk kayıt yöneticisi",
            "WhatsApp": "", "SMS Aktif": "", "Web Kullanıcı": username, "Web Şifre": "",
            "Rol": "ADMIN", "Yetki Kapsamı": "ALL", "Onay Seviyesi": "",
        }
        yeni_satir.update({
            "Sorumlu": username, "E-posta": e_posta.strip(), "Aktif": "Evet",
            "Web Kullanıcı": username, "Rol": "ADMIN", "Yetki Kapsamı": "ALL",
        })
        guncel = pd.concat([mevcut, pd.DataFrame([yeni_satir])], ignore_index=True) if not mevcut.empty else pd.DataFrame([yeni_satir])
        write_sheet("Mail_Listesi", guncel, kullanici="ONBOARDING", tenant_id=tenant_id)

    return {"tenant_id": tenant_id, "username": username}


def import_initial_data(tenant_id: str, excel_path: str, kullanici: str = "ONBOARDING") -> dict:
    """3. adım (isteğe bağlı): yüklenen Excel'i bu firmanın veritabanı
    alanına aktarır. Boş bırakılırsa firma, çekirdek sayfaları (Mağaza/
    Unvan/Norm) 'Tüm Sayfalar' panelinden elle de doldurabilir."""
    from services.input_excel_migration import migrate_excel_to_db
    tenant_id = tenant_id.strip().upper()
    if tenant_registry.get_tenant(tenant_id) is None:
        raise ValueError(f"'{tenant_id}' kodlu bir firma kaydı bulunamadı.")
    return migrate_excel_to_db(excel_path, kullanici=kullanici, tenant_id=tenant_id)
