create table if not exists public.omehr_sales_targets (
  tenant_id text not null,
  period text not null,
  store_id text not null,
  store_name text not null,
  sales_target numeric(18, 2) not null check (sales_target >= 0),
  explanation text,
  action_plan text,
  owner_name text,
  updated_by uuid not null default auth.uid(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, period, store_id)
);

alter table public.omehr_sales_targets enable row level security;

revoke all on table public.omehr_sales_targets from anon;
grant select, insert, update on table public.omehr_sales_targets to authenticated;

drop policy if exists "tenant members read sales targets" on public.omehr_sales_targets;
create policy "tenant members read sales targets"
on public.omehr_sales_targets
for select
to authenticated
using (
  exists (
    select 1 from public.omehr_user_access access
    where access.auth_user_id = (select auth.uid())
      and access.tenant_id = omehr_sales_targets.tenant_id
  )
);

drop policy if exists "sales management writes sales targets" on public.omehr_sales_targets;
create policy "sales management writes sales targets"
on public.omehr_sales_targets
for insert
to authenticated
with check (
  exists (
    select 1 from public.omehr_user_access access
    where access.auth_user_id = (select auth.uid())
      and access.tenant_id = omehr_sales_targets.tenant_id
      and upper(coalesce(access.role_code, '')) in ('ADMIN', 'SATIS_DIREKTORU', 'SATIŞ_DİREKTÖRÜ', 'SALES_DIRECTOR')
  )
);

drop policy if exists "sales management updates sales targets" on public.omehr_sales_targets;
create policy "sales management updates sales targets"
on public.omehr_sales_targets
for update
to authenticated
using (
  exists (
    select 1 from public.omehr_user_access access
    where access.auth_user_id = (select auth.uid())
      and access.tenant_id = omehr_sales_targets.tenant_id
      and upper(coalesce(access.role_code, '')) in ('ADMIN', 'SATIS_DIREKTORU', 'SATIŞ_DİREKTÖRÜ', 'SALES_DIRECTOR')
  )
)
with check (
  exists (
    select 1 from public.omehr_user_access access
    where access.auth_user_id = (select auth.uid())
      and access.tenant_id = omehr_sales_targets.tenant_id
      and upper(coalesce(access.role_code, '')) in ('ADMIN', 'SATIS_DIREKTORU', 'SATIŞ_DİREKTÖRÜ', 'SALES_DIRECTOR')
  )
);

create index if not exists omehr_sales_targets_tenant_period_idx
  on public.omehr_sales_targets (tenant_id, period desc);
