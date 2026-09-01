create table if not exists public.omehr_module_snapshots (
  tenant_id text not null,
  module_key text not null,
  payload jsonb not null default '{}'::jsonb,
  calculated_at timestamptz not null default now(),
  primary key (tenant_id, module_key)
);

alter table public.omehr_module_snapshots enable row level security;

revoke all on table public.omehr_module_snapshots from anon;
grant select on table public.omehr_module_snapshots to authenticated;

drop policy if exists "tenant members read module snapshots" on public.omehr_module_snapshots;
create policy "tenant members read module snapshots"
on public.omehr_module_snapshots
for select
to authenticated
using (
  exists (
    select 1
    from public.omehr_user_access access
    where access.auth_user_id = (select auth.uid())
      and access.tenant_id = omehr_module_snapshots.tenant_id
  )
);
