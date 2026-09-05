from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "vercel-ui"


def test_engine_authorization_is_scoped_to_active_tenant():
    route = (ROOT / "app/api/engine/run/route.ts").read_text(encoding="utf-8")
    page = (ROOT / "app/page.tsx").read_text(encoding="utf-8")

    assert "x-omehr-tenant-id" in route.lower()
    assert ".eq('tenant_id', tenantId)" in route
    assert "'X-OMEHR-Tenant-ID': access.tenant_id" in page


def test_navigation_clears_stale_engine_authorization_warning():
    page = (ROOT / "app/page.tsx").read_text(encoding="utf-8")

    assert "setError(''); setEngineMessage('')" in page
