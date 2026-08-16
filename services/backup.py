from __future__ import annotations

"""
OTOMATİK YEDEKLEME MODÜLÜ
============================
Input Excel dosyası her açılışta (refresh_home_proximity/recalculate_workbook
gibi dosyayı DEĞİŞTİREN her adımdan önce) `backups/` klasörüne zaman damgalı bir
kopyası alınır. Bir şey ters giderse (yanlış hücre silme, bozuk formül, vs.)
kullanıcı bu klasördeki en son sağlam kopyaya geri dönebilir.

Sadece SON N yedek tutulur (varsayılan 20); daha eskiler otomatik silinir, aksi
halde disk alanı sınırsız büyür.

P1 GÜÇLENDİRMELERİ (reviewer önerisi):
  - Her yedeğin SHA-256 özeti ayrı bir .sha256 dosyasına yazılır (bütünlük
    doğrulaması için — yedek dosya bozulmuşsa fark edilir).
  - Yedek alınırken Excel'in GERÇEKTEN AÇILABİLİR olduğu doğrulanır (bozuk
    bir kopyayı "yedek" diye saklamak, geri yüklemede işe yaramaz).
  - restore_backup() öncesi, o an DURAN dosyanın kendisi de otomatik olarak
    yedeklenir (restore'un kendisi de geri alınabilir olsun diye).
  - Her restore işlemi kalıcı bir denetim kaydına (kullanıcı+tarih) yazılır.
  - BASDAS_SECONDARY_BACKUP_DIR ortam değişkeni verilmişse, yedek AYRICA
    o (farklı disk/ağ) konuma da kopyalanır — en iyi çaba, hata akışı bozmaz.
"""

import hashlib
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from services.runtime_paths import runtime_root
from services.safe_exec import log_swallowed

# DÜZELTME: bu modül önceden ROOT'u her zaman kod kökü olarak
# (Path(__file__).resolve().parent.parent) hesaplıyordu — projedeki HER
# DİĞER services/*.py modülü (ai_operations_engine, main, report_mail_engine,
# model_governance, vb.) runtime_root()'u kullanırken bu tek modül
# kullanmıyordu. Sonucu: çoklu kiracı (multi-tenant) veya BASDAS_RUNTIME_ROOT
# ile izole edilmiş bir çalışma zamanında bile TÜM kiracıların input yedekleri
# ve restore_audit.json kaydı, izole runtime kökleri yerine kod köküne
# (backups/, logs/) yazılıyor, birbirine karışabiliyordu. runtime_root()
# kullanılarak diğer modüllerle tutarlı hâle getirildi.
def _backup_dir():
    from services.runtime_paths import runtime_root
    return runtime_root() / "backups"
def _restore_audit_log():
    from services.runtime_paths import runtime_root
    return runtime_root() / "logs" / "restore_audit.json"
DEFAULT_MAX_BACKUPS = 20


def _max_backups() -> int:
    """Tutulacak yedek sayısı — config_web.json'daki backup.max_backups
    ayarından okunur (Ayarlar ekranından değiştirilebilir); dosya/anahtar
    yoksa veya bozuksa DEFAULT_MAX_BACKUPS'a güvenle geri döner."""
    try:
        from services.app_settings import get_settings
        deger = int(get_settings().get("backup", {}).get("max_backups", DEFAULT_MAX_BACKUPS))
        return deger if deger > 0 else DEFAULT_MAX_BACKUPS
    except Exception as _exc:
        log_swallowed("services.backup._max_backups: beklenmeyen hata", _exc)
        return DEFAULT_MAX_BACKUPS


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for parca in iter(lambda: f.read(1 << 20), b""):
            h.update(parca)
    return h.hexdigest()


def _excel_acilabilir_mi(path: Path) -> bool:
    """Yedeğin GERÇEKTEN geçerli/açılabilir bir Excel dosyası olduğunu
    doğrular — bozuk bir kopyayı sessizce 'yedek' diye saklamamak için."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True)
        _ = wb.sheetnames  # en az sayfa listesini okuyabiliyor olmalı
        wb.close()
        return True
    except Exception as _exc:
        log_swallowed("services.backup._excel_acilabilir_mi: beklenmeyen hata", _exc)
        return False


def backup_input_file(path: Path, actor: str = "sistem") -> Path | None:
    """
    Verilen dosyanın zaman damgalı bir kopyasını backups/ klasörüne alır.
    Başarılıysa yedek dosyanın yolunu, değilse None döndürür. Hata durumunda
    ana akışı bozmamak için sessizce None döner (backup alınamaması, dosyanın
    okunmasını/işlenmesini engellemez).

    actor: bu yedeklemeyi tetikleyen kullanıcı adı (web panelinden "şimdi
    yenile" gibi bir eylemle tetiklendiyse); otomatik/motor tetiklemelerinde
    varsayılan "sistem" kullanılır. Her iki durumda da BAŞARILI bir
    yedekleme, services.web_runtime'daki değiştirilemez action_log'a
    "INPUT_BACKUP" olarak kalıcı biçimde kaydedilir (bkz. audit trigger'ları).
    """
    try:
        path = Path(path)
        if not path.is_file():
            return None
        _backup_dir().mkdir(parents=True, exist_ok=True)
        damga = datetime.now().strftime("%Y%m%d_%H%M%S")
        hedef = _backup_dir() / f"{path.stem}__{damga}{path.suffix}"
        shutil.copyfile(path, hedef)

        # DOĞRULAMA: yedek gerçekten açılabilir mi? Değilse, bozuk bir
        # kopyayı saklamak yerine SİLİNİR ve None döner.
        if not _excel_acilabilir_mi(hedef):
            from services.safe_exec import log_swallowed
            log_swallowed(f"backup_input_file: '{hedef}' açılabilir bir Excel değil — yedek reddedildi", ValueError("bozuk yedek"), level="ERROR")
            hedef.unlink(missing_ok=True)
            return None

        # BÜTÜNLÜK: SHA-256 özeti ayrı bir dosyaya yazılır.
        ozet = _sha256(hedef)
        (hedef.with_suffix(hedef.suffix + ".sha256")).write_text(ozet, encoding="utf-8")

        # İSTEĞE BAĞLI İKİNCİL KONUM: farklı bir disk/ağ yoluna da kopyala
        # (en iyi çaba — başarısız olursa akışı bozmaz).
        ikincil_yol = os.environ.get("BASDAS_SECONDARY_BACKUP_DIR")
        if ikincil_yol:
            try:
                ikincil_hedef = Path(ikincil_yol) / hedef.name
                ikincil_hedef.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(hedef, ikincil_hedef)
            except Exception as _exc:
                from services.safe_exec import log_swallowed
                log_swallowed(f"backup_input_file: ikincil konuma ('{ikincil_yol}') kopyalanamadı", _exc, level="WARNING")

        _eski_yedekleri_temizle(path)
        _audit_backup(actor, path, hedef)
        return hedef
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed(f"backup_input_file: '{path}' yedeklenemedi", _exc, level="ERROR")
        return None


def _audit_backup(actor: str, source: Path, hedef: Path) -> None:
    """Başarılı bir input yedeklemesini KALICI/değiştirilemez action_log'a
    yazar (bkz. services.web_runtime — audit trigger'ları UPDATE/DELETE'i
    reddeder). Bu adım isteğe bağlıdır (en iyi çaba): loglama başarısız
    olsa bile yedekleme işlemi zaten tamamlanmış sayılır, akış bozulmaz."""
    try:
        from services.web_runtime import log_web_action
        log_web_action(actor, "INPUT_BACKUP", f"{source.name} -> {hedef.name}")
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed("services.backup._audit_backup: beklenmeyen hata", _exc)


def _eski_yedekleri_temizle(path: Path) -> None:
    onek = f"{Path(path).stem}__"
    yedekler = sorted(
        (p for p in _backup_dir().glob(f"{onek}*{Path(path).suffix}") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for fazla in yedekler[_max_backups():]:
        try:
            fazla.unlink()
            (fazla.with_suffix(fazla.suffix + ".sha256")).unlink(missing_ok=True)
        except Exception as _exc:
            from services.safe_exec import log_swallowed
            log_swallowed(f"_eski_yedekleri_temizle: '{fazla}' silinemedi", _exc, level="INFO")


def list_backups(path: Path) -> list[Path]:
    """Bir dosyanın mevcut yedeklerini (en yeniden en eskiye) listeler."""
    onek = f"{Path(path).stem}__"
    if not _backup_dir().is_dir():
        return []
    return sorted(
        (p for p in _backup_dir().glob(f"{onek}*{Path(path).suffix}") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def verify_backup_integrity(backup_path: Path) -> bool:
    """Bir yedeğin, alındığı andaki SHA-256 özetiyle hâlâ eşleştiğini
    doğrular (dosya bozulmamış/değiştirilmemiş mi)."""
    backup_path = Path(backup_path)
    ozet_dosyasi = backup_path.with_suffix(backup_path.suffix + ".sha256")
    if not backup_path.is_file() or not ozet_dosyasi.is_file():
        return False
    try:
        beklenen = ozet_dosyasi.read_text(encoding="utf-8").strip()
        return _sha256(backup_path) == beklenen
    except Exception as _exc:
        log_swallowed("services.backup.verify_backup_integrity: beklenmeyen hata", _exc)
        return False


def _restore_denetim_kaydet(kayit: dict) -> None:
    try:
        _restore_audit_log().parent.mkdir(parents=True, exist_ok=True)
        gecmis = []
        if _restore_audit_log().is_file():
            try:
                gecmis = json.loads(_restore_audit_log().read_text(encoding="utf-8"))
            except Exception as _exc:
                log_swallowed("services.backup._restore_denetim_kaydet: beklenmeyen hata", _exc)
                gecmis = []
        gecmis.append(kayit)
        _restore_audit_log().write_text(json.dumps(gecmis, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as _exc:
        log_swallowed("services.backup._restore_denetim_kaydet: beklenmeyen hata", _exc)
        pass


def restore_audit_history(n: int = 50) -> list[dict]:
    """Denetim/gözlemlenebilirlik için son N restore işlemini döndürür."""
    if not _restore_audit_log().is_file():
        return []
    try:
        return json.loads(_restore_audit_log().read_text(encoding="utf-8"))[-n:][::-1]
    except Exception as _exc:
        log_swallowed("services.backup.restore_audit_history: beklenmeyen hata", _exc)
        return []


def restore_backup(backup_path: Path, target_path: Path, kullanici: str = "bilinmiyor") -> bool:
    """Seçilen yedeği hedef dosyanın üzerine geri yükler.

    P1 güçlendirmeleri: (1) geri yüklemeden ÖNCE o an duran dosyanın kendisi
    de otomatik yedeklenir (restore'un kendisi geri alınabilir olsun),
    (2) seçilen yedeğin bütünlüğü (SHA-256) doğrulanır, (3) işlem kalıcı
    bir denetim kaydına (kullanıcı+tarih+kaynak+hedef) yazılır."""
    backup_path = Path(backup_path)
    target_path = Path(target_path)
    zaman = datetime.now().isoformat(timespec="seconds")
    butunluk_ok = verify_backup_integrity(backup_path)
    try:
        # RESTORE ÖNCESİ OTOMATİK SNAPSHOT: mevcut dosya kaybolmasın.
        if target_path.is_file():
            backup_input_file(target_path, actor=kullanici)
        shutil.copyfile(backup_path, target_path)
        basarili = True
    except Exception as _exc:
        from services.safe_exec import log_swallowed
        log_swallowed(f"restore_backup: '{backup_path}' -> '{target_path}' geri yüklenemedi", _exc, level="ERROR")
        basarili = False
    _restore_denetim_kaydet({
        "zaman": zaman, "kullanici": kullanici,
        "kaynak_yedek": str(backup_path), "hedef": str(target_path),
        "yedek_butunlugu_dogrulandi": butunluk_ok, "basarili": basarili,
    })
    return basarili
