from __future__ import annotations

"""PERFORMANS LOGLAMA (OMEHR hızlandırma şartnamesi Madde 57-58).

Her sekme yüklemesi için: tab_name, load_time, cache_hit, render_time
kaydeder. Dosya: logs/performance.log (basit, insan tarafından
okunabilir tek satırlık kayıtlar — şartnamedeki örnek formatla
uyumlu: "21:12:03 GENERAL_OVERVIEW 0.41s").

Kullanım (web/app.py'nin sayfa dağıtım noktasında):
    with track_page_render(sayfa_adi, cache_hit=...):
        PAGE_RENDERERS[sayfa_adi](ctx)
"""

import time
from contextlib import contextmanager
from datetime import datetime


def _log_path():
    from services.runtime_paths import runtime_root
    return runtime_root() / "logs" / "performance.log"


def log_performance(tab_name: str, duration_seconds: float, *, cache_hit: bool | None = None,
                     excel_read_seconds: float | None = None) -> None:
    """Tek bir performans kaydını logs/performance.log'a ekler.

    Hata durumunda (log dizini yazılamıyorsa vb.) SESSİZCE yutulur —
    performans loglaması hiçbir zaman gerçek işlemi bozmamalıdır."""
    try:
        p = _log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        zaman = datetime.now().strftime("%H:%M:%S")
        parcalar = [zaman, tab_name, f"{duration_seconds:.2f}s"]
        if cache_hit is not None:
            parcalar.append("cache_hit=True" if cache_hit else "cache_hit=False")
        if excel_read_seconds is not None:
            parcalar.append(f"excel_read={excel_read_seconds:.2f}s")
        with p.open("a", encoding="utf-8") as fh:
            fh.write(" ".join(parcalar) + "\n")
    except Exception:
        pass


@contextmanager
def track_page_render(tab_name: str, *, cache_hit: bool | None = None):
    """Bir sayfa render işlemini zamanlar ve logs/performance.log'a yazar.

    Örnek:
        with track_page_render("Genel Özet"):
            render(ctx)
    """
    basla = time.perf_counter()
    try:
        yield
    finally:
        gecen = time.perf_counter() - basla
        log_performance(tab_name, gecen, cache_hit=cache_hit)


def cache_hit_rate(son_n: int = 200) -> float | None:
    """Madde 59: son N kayıttaki cache_hit oranını hesaplar (>%90 hedefi
    için). Log dosyası yoksa veya cache_hit hiç kaydedilmemişse None döner."""
    p = _log_path()
    if not p.is_file():
        return None
    try:
        satirlar = p.read_text(encoding="utf-8").strip().split("\n")[-son_n:]
    except Exception:
        return None
    isaretli = [s for s in satirlar if "cache_hit=" in s]
    if not isaretli:
        return None
    hit = sum(1 for s in isaretli if "cache_hit=True" in s)
    return hit / len(isaretli)
