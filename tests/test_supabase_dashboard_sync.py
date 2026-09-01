from __future__ import annotations

import json

from services import supabase_sync


class _Response:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_dashboard_sync_uses_neutral_tenant_and_upserts(monkeypatch):
    monkeypatch.setenv("OMEHR_SUPABASE_SYNC", "1")
    monkeypatch.setenv("OMEHR_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("OMEHR_SUPABASE_SECRET_KEY", "sb_secret_test")
    monkeypatch.setenv("OMEHR_TENANT_ID", "omehr")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return _Response()

    monkeypatch.setattr(supabase_sync, "urlopen", fake_urlopen)
    result = supabase_sync.sync_dashboard_summaries({
        "magaza_bazli": [{"magaza": "BUCA", "bolge_sorumlusu": "DERYA", "mevcut": 8, "norm": 11, "eksik": 3, "fazla": 0}],
        "unvan_bazli": [{"unvan": "KASİYER", "mevcut": 100, "norm": 110, "eksik": 10, "fazla": 0}],
    })

    assert result == {"stores": True, "titles": True, "modules": False}
    assert len(calls) == 2
    for request, timeout in calls:
        assert timeout == 12
        assert "on_conflict=" in request.full_url
        assert request.headers["Prefer"] == "resolution=merge-duplicates,return=minimal"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload[0]["tenant_id"] == "OMEHR_MAIN"


def test_kpi_sync_ignores_runtime_tenant_name(monkeypatch):
    monkeypatch.setenv("OMEHR_SUPABASE_SYNC", "1")
    monkeypatch.setenv("OMEHR_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("OMEHR_SUPABASE_SECRET_KEY", "sb_secret_test")
    monkeypatch.setenv("OMEHR_TENANT_ID", "omehr")
    payloads = []

    def fake_urlopen(request, timeout):
        payloads.append(json.loads(request.data.decode("utf-8")))
        return _Response()

    monkeypatch.setattr(supabase_sync, "urlopen", fake_urlopen)
    assert supabase_sync.sync_kpi_snapshot({"Aktif Mevcut": 600, "Toplam Norm": 607})
    assert payloads[0]["tenant_id"] == "OMEHR_MAIN"


def test_dashboard_sync_upserts_module_snapshots(monkeypatch):
    monkeypatch.setenv("OMEHR_SUPABASE_SYNC", "1")
    monkeypatch.setenv("OMEHR_SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("OMEHR_SUPABASE_SECRET_KEY", "sb_secret_test")
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return _Response()

    monkeypatch.setattr(supabase_sync, "urlopen", fake_urlopen)
    result = supabase_sync.sync_dashboard_summaries({
        "modules": {"personnel": {"title": "Personel", "rows": [{"Ad": "Demo"}]}},
    })

    assert result == {"stores": False, "titles": False, "modules": True}
    assert len(calls) == 1
    assert "omehr_module_snapshots?on_conflict=tenant_id,module_key" in calls[0].full_url
    payload = json.loads(calls[0].data.decode("utf-8"))
    assert payload[0]["tenant_id"] == "OMEHR_MAIN"
    assert payload[0]["module_key"] == "personnel"
