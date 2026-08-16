from __future__ import annotations

"""Performans loglama (Madde 57-59) — regresyon testleri."""

import time


def test_track_page_render_writes_log_entry(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.performance_log import track_page_render

    with track_page_render("TEST_SAYFA", cache_hit=True):
        time.sleep(0.01)

    log_dosyasi = tmp_path / "logs" / "performance.log"
    assert log_dosyasi.is_file()
    icerik = log_dosyasi.read_text(encoding="utf-8")
    assert "TEST_SAYFA" in icerik
    assert "cache_hit=True" in icerik


def test_performance_logging_never_raises_even_if_log_dir_unwritable(monkeypatch):
    """Şartname: performans loglaması hiçbir zaman gerçek işlemi bozmamalı."""
    from services.performance_log import log_performance
    monkeypatch.setattr("services.performance_log._log_path", lambda: __import__("pathlib").Path("/kesinlikle/olmayan/bir/dizin/x.log"))
    log_performance("HATA_TESTI", 1.0)  # istisna FIRLATMAMALI


def test_cache_hit_rate_computed_correctly(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    from services.performance_log import track_page_render, cache_hit_rate

    with track_page_render("A", cache_hit=True):
        pass
    with track_page_render("B", cache_hit=True):
        pass
    with track_page_render("C", cache_hit=False):
        pass

    oran = cache_hit_rate()
    assert oran == 2 / 3
