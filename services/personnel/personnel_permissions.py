from __future__ import annotations

"""Kullanıcı bazlı personel veri giriş yetkileri (FAST V15).

Merkezi Excel'in yanında saklanan, admin tarafından web panelinden
yönetilebilen bir yetki sistemi — hangi kullanıcının personel görüntüleme/
giriş/çıkış/düzenleme/ana veri/operasyon verisi/yetki yönetimi yapabileceğini
belirler. 3 PC aynı Excel'i (ve dolayısıyla aynı yetki dosyasını) paylaştığı
için tüm PC'lerde tutarlıdır.

DÜZELTME (çok kiracılı SaaS): Bu modül önceden 3 SABİT, gerçek bir firmaya
(@omehrmarket.com) ait e-posta adresini varsayılan yetki sahibi olarak koda
gömüyordu (`ikasistan@...`, `ikd@...`, `insankaynaklari@...`). Bu, HER
kiracının bu adreslerle eşleşen (ya da eşleşmeyen) kullanıcılarını yanlış
şekilde etkilerdi. Alttaki mekanizma (yapılandırılabilir, JSON tabanlı, admin
panelinden düzenlenebilir yetki sistemi) KORUNDU — yalnızca sabit e-posta
varsayılanları kaldırıldı. Her kiracı, kendi kullanıcılarına özel kısıtlama
istiyorsa (ör. "İK asistanı yalnız işe giriş yapabilsin") bunu KENDİ
panelinden, Ayarlar > Kullanıcı Veri Giriş Yetkileri ekranından tanımlar.
"""

from pathlib import Path
import json, os, tempfile

PERMISSIONS = {
    'personnel_view': 'Personel verilerini görüntüle',
    'personnel_entry': 'İşe giriş (tekli + toplu)',
    'personnel_exit': 'İşten çıkış (tekli + toplu)',
    'personnel_edit': 'Aktif personel kartını düzenle',
    'master_data': 'Ana veri / norm verisi düzenle',
    'operation_data': 'Operasyon verisi girişi',
    'permissions_admin': 'Kullanıcı veri giriş yetkilerini yönet',
}

# DÜZELTME: sabit firma e-postaları KALDIRILDI — her kiracı kendi
# varsayılanlarını Ayarlar ekranından tanımlar. Boş sözlük, aşağıdaki
# permissions_for()'daki rol tabanlı düşüşün (ADMIN/HR_DIRECTOR/
# IK_DIREKTORU = tam yetki, diğerleri = yalnız görüntüleme) tek başına
# yeterli, kiracıdan bağımsız varsayılan olmasını sağlar.
DEFAULTS: dict[str, list[str]] = {}


def _path(input_path: Path) -> Path:
    p = Path(input_path)
    return p.with_name('.omehr_user_permissions.json')


def _norm_email(email: str) -> str:
    return str(email or '').strip().casefold()


from functools import lru_cache


@lru_cache(maxsize=8)
def _load_permissions_file_cached(path_text: str, mtime_ns: int, size: int) -> dict[str, list[str]]:
    try:
        raw = json.loads(Path(path_text).read_text(encoding='utf-8'))
    except Exception:
        return {}
    out: dict[str, list[str]] = {}
    for email, perms in (raw.get('users') or {}).items():
        out[_norm_email(email)] = [x for x in perms if x in PERMISSIONS]
    return out


def load_permissions(input_path: Path) -> dict[str, list[str]]:
    """DÜZELTME (performans): önceden bu dosya HER izin kontrolünde (bir
    sayfa yüklemesinde 4 kez) yeniden okunup ayrıştırılıyordu. Artık
    dosyanın mtime+boyutuna göre önbelleklenir — yetkiler Ayarlar
    ekranından değiştirilince otomatik olarak taze okunur."""
    data = {k: list(v) for k, v in DEFAULTS.items()}
    p = _path(input_path)
    if p.exists():
        try:
            st_ = p.stat()
            data.update(_load_permissions_file_cached(str(p.resolve()), int(st_.st_mtime_ns), int(st_.st_size)))
        except Exception:
            pass
    return data


def permissions_for(input_path: Path, email: str, role: str = '') -> set[str]:
    e = _norm_email(email)
    r = str(role or '').strip().upper()
    configured = load_permissions(input_path)
    # Kiracının Ayarlar ekranından ÖZEL OLARAK tanımladığı bir kısıtlama
    # varsa (ör. "bu kullanıcı yalnız giriş yapabilsin"), role göre
    # GENİŞLETİLMEZ — kiracının kendi kararı esas alınır.
    if e in configured:
        return set(configured[e])
    # Hiçbir özel tanım yoksa güvenli varsayılan: yönetim rolleri tam
    # yetkili, diğerleri yalnız görüntüleme. Kiracı bunu Ayarlar
    # ekranından istediği gibi daraltıp genişletebilir.
    if r in {'ADMIN', 'HR_DIRECTOR', 'IK_DIREKTORU'}:
        return set(PERMISSIONS)
    return {'personnel_view'}


def can(input_path: Path, email: str, permission: str, role: str = '') -> bool:
    return permission in permissions_for(input_path, email, role)


def save_user_permissions(input_path: Path, users: dict[str, list[str]]) -> None:
    p = _path(input_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    merged = load_permissions(input_path)
    for email, perms in users.items():
        merged[_norm_email(email)] = [x for x in perms if x in PERMISSIONS]
    payload = {'version': 1, 'users': merged}
    fd, tmp = tempfile.mkstemp(prefix='omehr_perm_', suffix='.json', dir=str(p.parent))
    os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
        os.replace(tmp, p)
    finally:
        try:
            Path(tmp).unlink(missing_ok=True)
        except OSError:
            pass
