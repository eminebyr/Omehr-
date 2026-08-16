from __future__ import annotations

"""Ana motor için güvenli Excel yeniden hesaplama köprüsü.

LibreOffice kuruluysa input çalışma kitabını headless modda yeniden hesaplar.
Kurulu değilse motoru çökertmez; Python tarafındaki formül-bağımsız veri
zenginleştirme ile devam edilmesini sağlar.
"""
from services.excel_recalc import (
    is_recalc_available,
    last_successful_recalc,
    recalculate_workbook,
    soffice_version,
)
from services.runtime_paths import runtime_root
from services.settings import input_path


def recalculate_with_excel() -> dict:
    path = input_path(runtime_root())
    available = is_recalc_available()
    if not path.is_file():
        return {"status": "FAILED", "reason": f"Input bulunamadı: {path}", "file": str(path)}
    if not available:
        return {
            "status": "SKIPPED",
            "reason": "Python hesap motoru kullanıldı. LibreOffice isteğe bağlıdır.",
            "file": str(path),
        }
    ok = recalculate_workbook(path)
    return {
        "status": "SUCCESS" if ok else "WARNING",
        "file": str(path),
        "libreoffice": soffice_version(),
        "last_success": last_successful_recalc(),
        "reason": None if ok else "İsteğe bağlı Excel önbellek yenilemesi tamamlanamadı; Python hesap motoru kullanıldı.",
    }
