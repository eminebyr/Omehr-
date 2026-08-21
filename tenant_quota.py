"""KOTA UYGULAMASI — plan bazlı şube/kullanıcı sınırlarını FİİLEN uygular.

services/tenant_registry.py, her kiracı için `sube_kotasi`/`kullanici_kotasi`
DEĞERLERİNİ saklıyordu ama hiçbir yerde bu değerlere karşı gerçek bir
sayım/kontrol yapılmıyordu — bir kiracı planının izin verdiğinden fazla
şube veya kullanıcı ekleyebiliyordu. Bu modül, services/input_data_access.py
::write_sheet() içine bağlanarak bunu FİİLEN uygular.

Kasıtlı olarak dışarıda bırakılan: rapor sayısı kotası (roadmap'te
"kullanıcı, rapor" olarak anılıyor) — rapor üretimi tüketim bazlı bir
ölçüm gerektirir (aylık sayaç), bu modülün kapsamı yalnız STATİK sayılabilir
varlıklar (şube satırı, kullanıcı satırı) içindir.
"""
from __future__ import annotations


class KotaAsimiHatasi(Exception):
    """Bir kiracı, planının izin verdiği şube/kullanıcı sayısını aşmaya çalıştığında fırlatılır."""


def _kiraci_kotasi(tenant_id: str) -> dict | None:
    try:
        from services.tenant_registry import get_tenant
        return get_tenant(tenant_id)
    except Exception:
        # tenant_registry hiç kurulmamışsa (tek kiracılı/eski kurulum) kota
        # uygulanmaz — geriye dönük uyumluluk bilerek korunur.
        return None


def check_branch_quota(tenant_id: str, yeni_sube_sayisi: int) -> None:
    kayit = _kiraci_kotasi(tenant_id)
    if kayit is None:
        return
    kota = int(kayit.get("sube_kotasi") or 0)
    if kota > 0 and yeni_sube_sayisi > kota:
        raise KotaAsimiHatasi(
            f"'{tenant_id}' firması için şube kotası ({kota}) aşılıyor "
            f"(istenen: {yeni_sube_sayisi}). Planınızı yükseltin veya "
            f"mevcut şubelerden birini kaldırın."
        )


def check_user_quota(tenant_id: str, yeni_kullanici_sayisi: int) -> None:
    kayit = _kiraci_kotasi(tenant_id)
    if kayit is None:
        return
    kota = int(kayit.get("kullanici_kotasi") or 0)
    if kota > 0 and yeni_kullanici_sayisi > kota:
        raise KotaAsimiHatasi(
            f"'{tenant_id}' firması için kullanıcı kotası ({kota}) aşılıyor "
            f"(istenen: {yeni_kullanici_sayisi}). Planınızı yükseltin veya "
            f"mevcut kullanıcılardan birini kaldırın."
        )


# Kota kontrolü uygulanan sayfalar ve "satır sayımı" anlamına gelen ölçüt.
# Mail_Listesi'nde her satır bir web kullanıcısı DEĞİLDİR (bazı satırlar rol/
# yetki tanımı olabilir) — bu yüzden yalnız "Web Kullanıcı" alanı dolu ve
# benzersiz olan satırlar sayılır.
QUOTA_KONTROLLU_SAYFALAR = {"Dim_Magaza", "Mail_Listesi"}


def enforce_for_sheet(sheet_adi: str, df, tenant_id: str) -> None:
    """write_sheet() tarafından, DEĞİŞİKLİK VERİTABANINA YAZILMADAN ÖNCE
    çağrılır. Aşım varsa KotaAsimiHatasi fırlatır — write_sheet bu durumda
    hiçbir satırı silmez/yazmaz (transaction'a hiç başlanmaz)."""
    if sheet_adi == "Dim_Magaza":
        check_branch_quota(tenant_id, len(df))
    elif sheet_adi == "Mail_Listesi" and "Web Kullanıcı" in df.columns:
        benzersiz = df["Web Kullanıcı"].astype(str).str.strip()
        benzersiz = benzersiz[benzersiz.ne("") & benzersiz.ne("nan")].nunique()
        check_user_quota(tenant_id, benzersiz)
