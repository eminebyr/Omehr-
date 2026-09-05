from pathlib import Path


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def test_first_cloud_migration_creates_access_dependency_before_policy():
    sql = _sql("202609010001_create_module_snapshots.sql")
    access = sql.index("create table if not exists public.omehr_user_access")
    policy = sql.index('create policy "tenant members read module snapshots"')
    assert access < policy


def test_scoped_rls_does_not_leave_tenant_wide_module_access():
    sql = _sql("202609050001_complete_cloud_schema_and_scoped_rls.sql")
    assert 'drop policy if exists "tenant members read module snapshots"' in sql
    assert 'create policy "global users read module snapshots"' in sql
    assert "region_name = any(access.region_scope)" in sql
    assert "store_id = any(access.store_scope)" in sql


def test_all_vercel_summary_tables_are_reproducible_from_migrations():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in sorted(MIGRATIONS.glob("*.sql")))
    for table in (
        "omehr_user_access",
        "omehr_kpi_snapshot",
        "omehr_store_summary",
        "omehr_title_summary",
        "omehr_module_snapshots",
        "omehr_sales_targets",
    ):
        assert f"create table if not exists public.{table}" in combined
