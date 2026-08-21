"""GÜNCELLEME MEKANİZMASI — sürüm karşılaştırma, yedekleyerek güncelleme,
geri alma.

Kapsam ve dürüst sınırlar için lütfen önce bunu okuyun:

BU MODÜLÜN YAPTIĞI: Bir güncelleme paketini (yeni kod dosyalarını içeren
bir klasör) mevcut kuruluma UYGULAMADAN ÖNCE otomatik bir yedek alır,
YALNIZ KOD dosyalarını değiştirir (kullanıcı verisine — input/, data/,
logs/, output/, backups/, config_*.json — ASLA dokunmaz), ve bir sorun
olursa TEK KOMUTLA önceki sürüme geri döner. Tüm bu mantık saf Python +
dosya sistemi işlemleridir ve bu sandbox'ta GERÇEK dosya işlemleriyle
test edilmiştir (bkz. tests/test_updater.py).

BU MODÜLÜN YAPMADIĞI (dürüstçe — Windows ortamı gerektirir, burada
kurulamaz/test edilemez):
  - Tek tıkla çalışan bir "Setup.exe" — bu, PyInstaller/Inno Setup gibi
    araçlarla GERÇEK bir Windows makinesinde derlenmeli ve test edilmelidir.
  - Masaüstü kısayolu oluşturma (winshell/pywin32 gerektirir, Windows'a özgü).
  - Otomatik güncelleme kontrolü için bir dağıtım/indirme sunucusu — bu
    modül yalnız YEREL bir güncelleme paketi klasörünü uygulayabilir;
    "internetten yeni sürüm indir" kısmı ayrı bir altyapı kararıdır
    (nereye yükleneceği, kimlik doğrulama, CDN vb.).
  - "Lisans" doğrulaması — kod tabanında (bkz. services/app_settings.py
    modül docstring'i) hiçbir gerçek lisanslama kavramı yok; bu ayrı bir
    ürün kararı gerektirir.

Bu modül, KURULUM.bat/OMEHR_CURRENT_BASLAT.bat ile AYNI "batch launcher +
Python mantığı" desenini izler — GUNCELLEME_UYGULA.bat/.sh bu modülü
çağırır (bkz. proje kökü).
"""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from services.exceptions import ConfigurationError, WorkbookError

# Bir güncelleme paketi uygulanırken KOPYALANACAK klasör/dosya adları.
# Buradaki HER ŞEY üzerine yazılır — yalnız kod ve betikler.
UPDATE_INCLUDE = [
    "services", "web", "src", "deploy",
    "main.py", "worker.py", "ai_operations_engine.py", "report_mail_engine.py",
    "model_benchmark.py", "common_veri_okuma.py",
    "GUNCELLEME_UYGULA.py", "GUNCELLEME_UYGULA.bat", "GUNCELLEME_UYGULA.sh",
    "requirements.txt", "requirements.lock.txt", "requirements-postgres.txt",
    "config_features.json.example",  # örnek şablon, gerçek config DEĞİL
]

# ASLA dokunulmayacak — kullanıcı verisi ve kişiye özel yapılandırma.
UPDATE_EXCLUDE_ALWAYS = {
    "input", "data", "logs", "output", "backups", "archive",
    "config_web.json", "config_features.json", "config_integrations.json",
    "tenants.json", "assets",
}

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def _version_tuple(v: str) -> tuple[int, int, int]:
    m = _VERSION_RE.match(v.strip())
    if not m:
        raise ConfigurationError(f"Geçersiz sürüm biçimi: '{v}' (beklenen: X.Y.Z)")
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]


def compare_versions(a: str, b: str) -> int:
    """a<b ise -1, a==b ise 0, a>b ise 1 döner."""
    ta, tb = _version_tuple(a), _version_tuple(b)
    return (ta > tb) - (ta < tb)


def current_version() -> str:
    from services.version import APP_VERSION

    return APP_VERSION


@dataclass
class UpdateResult:
    onceki_surum: str
    yeni_surum: str
    yedek_yolu: Path
    kopyalanan_ogeler: list[str] = field(default_factory=list)
    basarili: bool = True
    hata: str | None = None


def create_pre_update_snapshot(root: Path, snapshot_dir: Path | None = None) -> Path:
    """Güncellemeden ÖNCE, mevcut KOD dosyalarının (kullanıcı verisi HARİÇ)
    zaman damgalı bir anlık görüntüsünü alır. Dönüş: anlık görüntü klasörü.
    """
    root = Path(root)
    hedef_kok = Path(snapshot_dir) if snapshot_dir else root / "backups" / "guncelleme_oncesi"
    damga = datetime.now().strftime("%Y%m%d_%H%M%S")
    hedef = hedef_kok / f"snapshot_{current_version()}_{damga}"
    hedef.mkdir(parents=True, exist_ok=True)

    for ad in UPDATE_INCLUDE:
        kaynak = root / ad
        if not kaynak.exists():
            continue
        varis = hedef / ad
        if kaynak.is_dir():
            shutil.copytree(kaynak, varis, dirs_exist_ok=True)
        else:
            varis.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kaynak, varis)

    (hedef / "_snapshot_meta.json").write_text(
        json.dumps({"surum": current_version(), "alinma_zamani": datetime.now().isoformat()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return hedef


def apply_update(update_package_dir: Path, root: Path, new_version: str) -> UpdateResult:
    """update_package_dir'daki KOD dosyalarını root'a uygular.

    Adımlar: (1) mevcut kodun anlık görüntüsünü al, (2) yalnız
    UPDATE_INCLUDE'daki öge adlarını, UPDATE_EXCLUDE_ALWAYS'i asla
    ezmeden kopyala, (3) başarısız olursa OTOMATİK ROLLBACK yap.
    Kullanıcı verisine (input/data/logs/output/backups/config_*.json)
    KESİNLİKLE dokunulmaz.
    """
    root = Path(root)
    update_package_dir = Path(update_package_dir)
    if not update_package_dir.is_dir():
        raise WorkbookError(f"Güncelleme paketi klasörü bulunamadı: {update_package_dir}")

    onceki_surum = current_version()
    try:
        yedek = create_pre_update_snapshot(root)
    except Exception as exc:
        # Yedek ALINAMADIYSA güncellemeye hiç BAŞLAMIYORUZ — yedeksiz
        # bir güncelleme denemek, geri dönüşü imkânsız bir risktir.
        return UpdateResult(
            onceki_surum=onceki_surum, yeni_surum=new_version,
            yedek_yolu=Path(), kopyalanan_ogeler=[], basarili=False,
            hata=(
                f"Güncelleme öncesi yedek alınamadı ({type(exc).__name__}: {exc}) — "
                "güvenlik nedeniyle güncelleme İPTAL edildi, hiçbir dosya değiştirilmedi."
            ),
        )
    kopyalanan: list[str] = []

    try:
        for ad in UPDATE_INCLUDE:
            if ad in UPDATE_EXCLUDE_ALWAYS:
                continue  # güvenlik: bir yönetici UPDATE_INCLUDE'a yanlışlıkla
                # kullanıcı verisi eklerse bile ASLA ezilmez.
            kaynak = update_package_dir / ad
            if not kaynak.exists():
                continue  # paket bu ögeyi içermiyor, dokunma
            hedef = root / ad
            if kaynak.is_dir():
                shutil.copytree(kaynak, hedef, dirs_exist_ok=True)
            else:
                hedef.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(kaynak, hedef)
            kopyalanan.append(ad)

        return UpdateResult(
            onceki_surum=onceki_surum, yeni_surum=new_version,
            yedek_yolu=yedek, kopyalanan_ogeler=kopyalanan, basarili=True,
        )
    except Exception as exc:
        # OTOMATİK GERİ ALMA: güncelleme yarıda kaldıysa kurulumu
        # bozuk bırakmak yerine hemen önceki hâline döndür.
        #
        # ÖNEMLİ: rollback()'in KENDİSİ de başarısız olabilir (ör. aynı
        # disk hatası hem güncellemeyi hem geri almayı etkiliyorsa). Bu
        # durumda hatayı YUTMAK yerine (kurulumun BOZUK ama sessizce
        # "başarılı" görünmesi çok daha tehlikeli olurdu) her iki hatayı
        # da açıkça bildiriyoruz; kurulum bu noktada MANUEL müdahale
        # gerektirebilir — yedek yolu (yedek_yolu) elle geri yükleme
        # için kullanıcıya veriliyor.
        try:
            rollback(yedek, root)
            hata_metni = f"{type(exc).__name__}: {exc} — otomatik olarak {onceki_surum} sürümüne geri dönüldü."
        except Exception as rollback_exc:
            hata_metni = (
                f"KRİTİK: güncelleme başarısız oldu ({type(exc).__name__}: {exc}) VE "
                f"otomatik geri alma da başarısız oldu ({type(rollback_exc).__name__}: {rollback_exc}). "
                f"Kurulum tutarsız durumda olabilir — MANUEL olarak şu yedekten geri yükleyin: {yedek}"
            )
        return UpdateResult(
            onceki_surum=onceki_surum, yeni_surum=new_version,
            yedek_yolu=yedek, kopyalanan_ogeler=kopyalanan,
            basarili=False, hata=hata_metni,
        )


def rollback(snapshot_dir: Path, root: Path) -> None:
    """create_pre_update_snapshot() ile alınmış bir anlık görüntüyü
    root'a geri yükler. Kullanıcı verisine dokunmaz (anlık görüntü zaten
    yalnız kod dosyalarını içerir)."""
    snapshot_dir = Path(snapshot_dir)
    root = Path(root)
    if not snapshot_dir.is_dir():
        raise WorkbookError(f"Geri yükleme için anlık görüntü bulunamadı: {snapshot_dir}")

    for ad in UPDATE_INCLUDE:
        if ad in UPDATE_EXCLUDE_ALWAYS:
            continue
        kaynak = snapshot_dir / ad
        if not kaynak.exists():
            continue
        hedef = root / ad
        if kaynak.is_dir():
            if hedef.exists():
                shutil.rmtree(hedef)
            shutil.copytree(kaynak, hedef)
        else:
            hedef.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(kaynak, hedef)
