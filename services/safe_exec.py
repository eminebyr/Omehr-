from __future__ import annotations

"""
SESSİZ HATA YUTMA — MERKEZİ LOGLAMA KATMANI
================================================
Sorun: Kod tabanında (özellikle engine_core.py, web/app.py, backup.py,
formula_bagimsiz_hesapla.py, region_access.py, kpi_history.py) çok sayıda
"except Exception: pass" bloğu var. Bunların çoğu BİLEREK ana akışı
bozmamak için var (doğru tasarım kararı) — ama hatayı TAMAMEN SESSİZCE
yutuyorlar, hiçbir yerde iz bırakmıyorlar. Bu, gerçek bir sorun oluştuğunda
(ör. bir hesaplama adımı sessizce atlandığında) kimsenin fark etmemesine
yol açar.

Bu modül, "pass" yerine kullanılacak bir CONTEXT MANAGER sağlar: hatayı
YİNE YUTAR (akışı bozmaz, davranış aynı kalır) ama artık logs/BASDAS_CURRENT.log
dosyasına HANGİ bağlamda, HANGİ hatanın oluştuğunu yazar. Böylece "sessiz"
olan sadece kullanıcı arayüzüdür — geliştirici/denetim için hiçbir şey
sessiz değildir.
"""

import logging
from contextlib import contextmanager

from services.observability import get_logger

_LOGGER = get_logger("basdas.sessiz_hata")


@contextmanager
def swallow(context: str, level: str = "WARNING", reraise: bool = False):
    """'except Exception: pass' yerine kullanılır.

    Kullanım:
        with swallow("refresh_home_proximity: koordinat güncelleme"):
            refresh_home_proximity(path)

    Hata oluşursa AKIŞ BOZULMAZ (pass ile aynı davranış) ama
    logs/BASDAS_CURRENT.log'a bağlam + hata tipi + mesaj yazılır.
    reraise=True verilirse, loglama sonrası hata yeniden fırlatılır
    (gerçekten KRİTİK noktalarda "sessizce devam etme" yerine durdurmak
    için kullanılır).
    """
    try:
        yield
    except Exception as exc:
        seviye = getattr(logging, level.upper(), logging.WARNING)
        _LOGGER.log(seviye, "[%s] Yutulan hata: %s: %s", context, type(exc).__name__, exc)
        if reraise:
            raise


def log_swallowed(context: str, exc: BaseException, level: str = "WARNING") -> None:
    """swallow() context manager'ının kullanılamadığı yerlerde (ör. except
    bloğu içinde belirli bir değer return etmesi gerektiğinde) DOĞRUDAN
    çağrılabilecek basit loglama fonksiyonu:

        try:
            ...
        except Exception as exc:
            log_swallowed("bağlam açıklaması", exc)
            return False
    """
    seviye = getattr(logging, level.upper(), logging.WARNING)
    _LOGGER.log(seviye, "[%s] Yutulan hata: %s: %s", context, type(exc).__name__, exc)


def recent_swallowed_errors(n: int = 50) -> list[str]:
    """Denetim/gözlemlenebilirlik için: log dosyasındaki son 'Yutulan hata'
    kayıtlarını döndürür (ör. sistem sağlığı panelinde göstermek için)."""
    log_path = get_logger().handlers[0].baseFilename if get_logger().handlers else None
    if not log_path:
        return []
    try:
        from pathlib import Path
        lines = Path(log_path).read_text(encoding="utf-8", errors="ignore").splitlines()
        return [l for l in lines if "Yutulan hata" in l][-n:]
    except Exception:
        return []
