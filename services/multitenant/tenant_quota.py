"""KOTA UYGULAMASI (enforcement) — write_sheet() üzerinden fiilen
uygulanır.

DÜZELTME: tenant_registry.py'nin sube_kotasi/kullanici_kotasi alanları
önceden yalnız SAKLANIYORDU, hiçbir yerde KONTROL EDİLMİYORDU — bir
kiracı sınırsız şube/kullanıcı ekleyebiliyordu (faturalama planının
pratikte hiçbir anlamı yoktu). Bu modül, services/input_data_access.py
::write_sheet() içinden HER yazma öncesi çağrılır.
"""
from __future__ import annotations

from services.multitenant.tenant_registry import check_quota


class KotaAsimiHatasi(Exception):
    """Bir kiracının plan kotası (şube veya kullanıcı sayısı) aşıldığında
    fırlatılır. Yazma işlemi bu istisna ile İPTAL edilir — önceki
    geçerli veri BOZULMAZ (write_sheet, bu istisnayı yakalamadan önce
    hiçbir kalıcı değişiklik yapmamış olmalıdır)."""


# Hangi sayfa hangi kota türünü temsil eder — yeni bir "şube" ya da
# "kullanıcı" sayısı sayfası eklenirse burası genişletilmelidir.
_SUBE_SAYFALARI = {"Dim_Magaza"}
_KULLANICI_SAYFALARI = {"Mail_Listesi"}


def check_branch_quota(tenant_id: str, mevcut_sayi: int) -> None:
    ok, hata = check_quota(tenant_id, "sube", mevcut_sayi)
    if not ok:
        raise KotaAsimiHatasi(hata)


def check_user_quota(tenant_id: str, mevcut_sayi: int) -> None:
    ok, hata = check_quota(tenant_id, "kullanici", mevcut_sayi)
    if not ok:
        raise KotaAsimiHatasi(hata)


def enforce_for_sheet(sheet_adi: str, df, tenant_id: str) -> None:
    """write_sheet() içinden HER yazma öncesi çağrılır. Yalnız şube/
    kullanıcı sayısını temsil eden sayfalar için kota kontrolü yapar —
    diğer tüm sayfalar (Fact_Norm, Fact_Mevcut vb.) etkilenmez."""
    if sheet_adi in _SUBE_SAYFALARI:
        check_branch_quota(tenant_id, len(df))
    elif sheet_adi in _KULLANICI_SAYFALARI:
        check_user_quota(tenant_id, len(df))
