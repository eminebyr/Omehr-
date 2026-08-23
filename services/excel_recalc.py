from __future__ import annotations

"""
EXCEL FORMÜL YENİDEN HESAPLAMA MOTORU
========================================
openpyxl formülleri HESAPLAMAZ; sadece formül metnini yazar. Bir formül
hücresinin pandas/openpyxl(data_only=True) ile okunabilmesi için, o hücrenin
önbelleğe alınmış (cached) bir SONUÇ değerine sahip olması gerekir. Bu değer
sadece gerçek bir hesap motoru (Excel veya LibreOffice Calc) dosyayı AÇIP
HESAPLADIĞINDA üretilir.

Bu modül, input Excel dosyasını LibreOffice (soffice) ile arka planda (headless)
açıp tüm formülleri zorla yeniden hesaplatır ve SONUCU dosyanın üzerine yazar.
Taşınabilir bir LibreOffice kullanıcı profili (reference/lo_profile) kullanılır;
bu profilde "dosya açılışında her zaman yeniden hesapla" ayarı önceden
etkinleştirilmiştir (OOXMLRecalcMode=2). Bu sayede sistemin çalıştığı HER
bilgisayarda (kullanıcının kendi makinesi dahil) aynı davranış garanti edilir,
global LibreOffice ayarlarına bağımlı kalınmaz.

NOT: Bu işlem masaüstü sınıfı bir makinede ortalama 60-150 saniye sürebilir
(dosyanın boyutuna, sayfa/formül sayısına göre değişir). Bu, "her zaman canlı,
doğru formül sonucu" garantisi karşılığında bilinçli olarak kabul edilmiş bir
performans maliyetidir.
"""

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from services.safe_exec import log_swallowed

ROOT = Path(__file__).resolve().parent.parent
LO_PROFILE_DIR = ROOT / "reference" / "lo_profile"
RECALC_TIMEOUT_SECONDS = 240


def _file_sha256(path: Path) -> str:
    """Dosyanın içerik hash'i — SADECE bu hash değiştiğinde LibreOffice'i
    yeniden çağırmak için kullanılır (V19.8 sertleştirme: mtime yerine
    içerik hash'i — mtime dosya kopyalama/senkronizasyon gibi işlemlerde
    içerik değişmeden de değişebilir, hash değişmez)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _soffice_binary() -> str | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    return None


def is_recalc_available() -> bool:
    """LibreOffice bu makinede kurulu mu, kontrol eder."""
    return _soffice_binary() is not None


_LAST_SUCCESS_MARKER = ROOT / "logs" / ".son_basarili_formul_hesaplama.json"


def soffice_version() -> str | None:
    """Kurulu LibreOffice'in sürüm metnini döndürür (health-check için).
    Kurulu değilse veya sürüm sorgusu başarısız olursa None döner."""
    binary = _soffice_binary()
    if not binary:
        return None
    try:
        result = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=15)
        return result.stdout.strip() or result.stderr.strip() or None
    except Exception as _exc:
        log_swallowed("services.excel_recalc.soffice_version: beklenmeyen hata", _exc)
        return None


def last_successful_recalc() -> dict | None:
    """En son BAŞARILI formül hesaplamasının ne zaman olduğunu (health-check
    ve gözlemlenebilirlik için) döndürür. Hiç başarılı hesaplama olmadıysa
    None döner."""
    if not _LAST_SUCCESS_MARKER.is_file():
        return None
    try:
        return json.loads(_LAST_SUCCESS_MARKER.read_text(encoding="utf-8"))
    except Exception as _exc:
        log_swallowed("services.excel_recalc.last_successful_recalc: beklenmeyen hata", _exc)
        return None


def _son_basariyi_kaydet(path: Path, source_hash: str | None = None) -> None:
    try:
        _LAST_SUCCESS_MARKER.parent.mkdir(parents=True, exist_ok=True)
        _LAST_SUCCESS_MARKER.write_text(
            json.dumps({
                "zaman": datetime.now().isoformat(timespec="seconds"),
                "dosya": str(path),
                "source_hash": source_hash,
                "libreoffice_surumu": soffice_version(),
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as _exc:
        log_swallowed("services.excel_recalc._son_basariyi_kaydet: beklenmeyen hata", _exc)
        pass


def recalculate_workbook(path: Path, timeout: int = RECALC_TIMEOUT_SECONDS) -> bool:
    """
    Verilen Excel dosyasındaki tüm formülleri LibreOffice ile zorla yeniden
    hesaplar ve SONUÇLARI (formülleri koruyarak) dosyanın üzerine kaydeder.

    Döndürür: başarılıysa True, LibreOffice bulunamazsa veya hata olursa False
    (bu durumda dosya olduğu gibi bırakılır; formül hücreleri boş/eski
    görünebilir ama sistem çökmez).
    """
    path = Path(path).resolve()
    if not path.is_file():
        return False

    # PERFORMANS/SERTLEŞTIRME: dosya son başarılı hesaplamadan beri hiç
    # değişmediyse (içerik hash'i aynıysa) LibreOffice'i tekrar tetikleme.
    onceki = last_successful_recalc()
    guncel_hash = _file_sha256(path)
    if onceki and onceki.get("dosya") == str(path) and onceki.get("source_hash") == guncel_hash:
        return True

    binary = _soffice_binary()
    if binary is None:
        return False

    with tempfile.TemporaryDirectory(prefix="omehr_recalc_") as tmp_dir:
        cmd = [
            binary,
            "--headless",
            "--invisible",
            "--nocrashreport",
            "--nodefault",
            "--norestore",
            "--nofirststartwizard",
            "--nologo",
            f"-env:UserInstallation=file://{LO_PROFILE_DIR}",
            "--convert-to",
            "xlsx",
            "--outdir",
            tmp_dir,
            str(path),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (subprocess.TimeoutExpired, OSError):
            return False

        if result.returncode != 0:
            return False

        out_file = Path(tmp_dir) / path.name
        if not out_file.is_file():
            return False

        shutil.copyfile(out_file, path)
        _son_basariyi_kaydet(path, _file_sha256(path))
        return True
