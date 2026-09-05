from services import supabase_sync


def test_empty_module_does_not_overwrite_last_valid_snapshot(monkeypatch):
    posted = []

    def fake_post(table, payload, *, upsert=False):
        posted.append((table, payload, upsert))
        return True

    monkeypatch.setattr(supabase_sync, "_post_rows", fake_post)
    result = supabase_sync.sync_dashboard_summaries({
        "modules": {
            "operations": {"title": "Operasyon", "rows": []},
            "personnel": {"title": "Personel", "rows": [{"PersonelID": "P1"}]},
        }
    })

    module_payload = next(payload for table, payload, _ in posted if table == "omehr_module_snapshots")
    assert [row["module_key"] for row in module_payload] == ["personnel"]
    assert result["modules"] is True
