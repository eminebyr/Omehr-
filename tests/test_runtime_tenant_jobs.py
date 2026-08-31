from __future__ import annotations


def test_worker_uses_job_tenant_and_restores_environment(monkeypatch):
    import os
    import worker

    observed = []

    def fake_execute(job):
        observed.append(os.environ.get("OMEHR_TENANT"))
        return {"ok": True}

    monkeypatch.setattr(worker, "_execute_for_tenant", fake_execute)
    monkeypatch.setenv("OMEHR_TENANT", "ORIGINAL")

    assert worker.execute({"tenant": "FIRMA_A", "job_type": "TEST", "payload": {}}) == {"ok": True}
    assert observed == ["FIRMA_A"]
    assert os.environ["OMEHR_TENANT"] == "ORIGINAL"


def test_scheduled_job_is_unique_per_tenant_and_slot(isolated_root):
    # DÜZELTME: services/job_queue.py'deki modül-seviyesi "DB" sabiti
    # kaldırıldı (bkz. job_queue.py'deki gerekçe — path doubling/stale DB
    # kaynağı bug'ı). Artık DB yolu her çağrıda taze runtime_root()'tan
    # hesaplanıyor; bu yüzden test izolasyonu da projedeki diğer tüm
    # testlerle AYNI şekilde (isolated_root fixture'ı ile OMEHR_RUNTIME_ROOT
    # ortam değişkenini geçici bir klasöre yönlendirerek) yapılır —
    # job_queue.DB'yi doğrudan monkeypatch etmek yerine.
    from services import job_queue

    first = job_queue.enqueue_scheduled_once("RUN_REPORTS", {}, "FIRMA_A", "2026-08-29T10:00")
    duplicate = job_queue.enqueue_scheduled_once("RUN_REPORTS", {}, "FIRMA_A", "2026-08-29T10:00")
    other_tenant = job_queue.enqueue_scheduled_once("RUN_REPORTS", {}, "FIRMA_B", "2026-08-29T10:00")

    assert first is not None
    assert duplicate is None
    assert other_tenant is not None