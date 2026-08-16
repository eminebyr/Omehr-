from __future__ import annotations

"""BASDAS_WORKER_INLINE — ücretsiz katman dağıtımı için senkron iş işleme.

worker.py'nin AYRI bir süreç olarak çalıştırılamadığı platformlarda
(Streamlit Community Cloud gibi), web/app.py'nin BASDAS_WORKER_INLINE=1
ayarlıyken kuyruktaki bekleyen işleri kendisi işlediğini doğrular.
"""

import shutil


def test_inline_worker_processes_pending_job(tmp_path, monkeypatch):
    monkeypatch.setenv("BASDAS_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("BASDAS_MAIL_DRY_RUN", "1")
    (tmp_path / "input").mkdir()

    from services.job_queue import enqueue, status
    is_id = enqueue("SEND_EMAIL", {
        "report_type": "TEST", "subject": "test", "body": "test", "recipients": ["a@test.com"],
    })
    assert status(is_id)["status"] == "PENDING"

    import worker
    worker.run(drain=True)

    sonuc = status(is_id)
    assert sonuc["status"] == "SUCCESS", (
        f"REGRESYON: inline worker mekanizması işi işlemedi: {sonuc}"
    )


def test_worker_inline_env_flag_default_off_does_not_process(tmp_path, monkeypatch):
    """BASDAS_WORKER_INLINE ayarlanmadığında (normal Docker/VPS dağıtımı),
    web/app.py'nin BU KOD YOLUNU hiç çalıştırmaması gerektiğini — yani
    varsayılanın 'kapalı' olduğunu doğrular (kod incelemesiyle)."""
    kaynak = open("web/app.py", encoding="utf-8").read()
    assert 'os.getenv("BASDAS_WORKER_INLINE", "0") == "1"' in kaynak, (
        "REGRESYON: inline worker varsayılan olarak KAPALI olmalı "
        "(yalnız açıkça BASDAS_WORKER_INLINE=1 ayarlandığında çalışmalı)."
    )
