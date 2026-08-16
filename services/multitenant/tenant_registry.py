"""KİRACI KAYDI (tenant registry) — veritabanı tabanlı.

tenants.json (services/tenant_manager.py) dosya/süreç tabanlı dağıtım
için hâlâ kullanılabilir kalır (geriye dönük uyumluluk) — ama gerçek
SaaS'ta plan/kota/faturalama durumu bir JSON dosyasında değil,
veritabanında, sorgulanabilir ve GÜNCELLENEBİLİR olmalıdır. Bu modül o
tabloyu kurar ve yönetir.
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.db_backend import connect, backend_name
from services.runtime_paths import runtime_root

_GECERLI_PLANLAR = {"deneme", "temel", "standart", "kurumsal"}
_GECERLI_DURUMLAR = {"aktif", "askida", "iptal"}


def _sqlite_path():
    return runtime_root() / "data" / "input_data.db"


def ensure_schema() -> None:
    backend = backend_name()
    if backend == "postgres":
        id_tanimi = "id SERIAL PRIMARY KEY"
    else:
        id_tanimi = "id INTEGER PRIMARY KEY AUTOINCREMENT"
    con = connect(_sqlite_path())
    try:
        con.execute(
            f'''CREATE TABLE IF NOT EXISTS tenants (
                {id_tanimi},
                tenant_id TEXT NOT NULL UNIQUE,
                ad TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'deneme',
                durum TEXT NOT NULL DEFAULT 'aktif',
                sube_kotasi INTEGER NOT NULL DEFAULT 10,
                kullanici_kotasi INTEGER NOT NULL DEFAULT 5,
                olusturulma_zamani TEXT NOT NULL
            )'''
        )
        con.commit()
    finally:
        con.close()


def create_tenant(tenant_id: str, ad: str, plan: str = "deneme",
                   sube_kotasi: int = 10, kullanici_kotasi: int = 5) -> dict:
    tenant_id = tenant_id.strip().upper()
    if not tenant_id:
        raise ValueError("tenant_id boş olamaz.")
    if plan not in _GECERLI_PLANLAR:
        raise ValueError(f"Geçersiz plan: {plan}. Geçerli: {sorted(_GECERLI_PLANLAR)}")
    ensure_schema()
    con = connect(_sqlite_path())
    try:
        mevcut = con.execute("SELECT tenant_id FROM tenants WHERE tenant_id=?", (tenant_id,)).fetchone()
        if mevcut:
            raise ValueError(f"'{tenant_id}' kodlu kiracı zaten kayıtlı.")
        zaman = datetime.now(timezone.utc).isoformat(timespec="seconds")
        con.execute(
            "INSERT INTO tenants(tenant_id, ad, plan, durum, sube_kotasi, kullanici_kotasi, olusturulma_zamani) "
            "VALUES (?,?,?,?,?,?,?)",
            (tenant_id, ad, plan, "aktif", sube_kotasi, kullanici_kotasi, zaman),
        )
        con.commit()
        return {"tenant_id": tenant_id, "ad": ad, "plan": plan, "durum": "aktif",
                "sube_kotasi": sube_kotasi, "kullanici_kotasi": kullanici_kotasi}
    finally:
        con.close()


def get_tenant(tenant_id: str) -> dict | None:
    ensure_schema()
    con = connect(_sqlite_path())
    try:
        row = con.execute(
            "SELECT tenant_id, ad, plan, durum, sube_kotasi, kullanici_kotasi, olusturulma_zamani "
            "FROM tenants WHERE tenant_id=?",
            (tenant_id.strip().upper(),),
        ).fetchone()
        if row is None:
            return None
        return dict(row) if hasattr(row, "keys") else {
            "tenant_id": row[0], "ad": row[1], "plan": row[2], "durum": row[3],
            "sube_kotasi": row[4], "kullanici_kotasi": row[5], "olusturulma_zamani": row[6],
        }
    finally:
        con.close()


def list_tenants() -> list[dict]:
    ensure_schema()
    con = connect(_sqlite_path())
    try:
        rows = con.execute(
            "SELECT tenant_id, ad, plan, durum, sube_kotasi, kullanici_kotasi, olusturulma_zamani "
            "FROM tenants ORDER BY olusturulma_zamani"
        ).fetchall()
        sonuc = []
        for row in rows:
            sonuc.append(dict(row) if hasattr(row, "keys") else {
                "tenant_id": row[0], "ad": row[1], "plan": row[2], "durum": row[3],
                "sube_kotasi": row[4], "kullanici_kotasi": row[5], "olusturulma_zamani": row[6],
            })
        return sonuc
    finally:
        con.close()


def is_active(tenant_id: str) -> bool:
    kayit = get_tenant(tenant_id)
    return bool(kayit) and kayit["durum"] == "aktif"


def check_quota(tenant_id: str, kota_turu: str, mevcut_sayi: int) -> tuple[bool, str]:
    """DÜZELTME: sube_kotasi/kullanici_kotasi alanları önceden tabloda
    TANIMLI ama HİÇBİR yerde UYGULANMIYORDU — bir kiracı sınırsız mağaza/
    kullanıcı ekleyebiliyordu (faturalama planının hiçbir anlamı yoktu).
    kota_turu: 'sube' veya 'kullanici'. mevcut_sayi: EKLEME SONRASI
    olacak toplam sayı (yani "şu an N var, +1 eklenirse N+1 mi geçilir?"
    şeklinde çağrılmalı). Kiracı kaydı yoksa (tek kiracılı/eski kurulum)
    kontrol atlanır — geriye dönük uyumluluk bilerek korunur."""
    kayit = get_tenant(tenant_id)
    if kayit is None:
        return True, ""
    if kota_turu == "sube":
        limit = int(kayit["sube_kotasi"])
        etiket = "şube"
    elif kota_turu == "kullanici":
        limit = int(kayit["kullanici_kotasi"])
        etiket = "kullanıcı"
    else:
        raise ValueError(f"Geçersiz kota türü: {kota_turu}")
    if mevcut_sayi > limit:
        return False, (
            f"'{kayit['ad']}' firmasının {kayit['plan']} planı en fazla {limit} {etiket} "
            f"desteklemektedir (istenen: {mevcut_sayi}). Kotayı artırmak için plan yükseltme gerekir."
        )
    return True, ""


def set_status(tenant_id: str, durum: str) -> None:
    if durum not in _GECERLI_DURUMLAR:
        raise ValueError(f"Geçersiz durum: {durum}. Geçerli: {sorted(_GECERLI_DURUMLAR)}")
    ensure_schema()
    con = connect(_sqlite_path())
    try:
        con.execute("UPDATE tenants SET durum=? WHERE tenant_id=?", (durum, tenant_id.strip().upper()))
        con.commit()
    finally:
        con.close()
