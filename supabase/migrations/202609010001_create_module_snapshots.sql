-- İlk migration kendi RLS bağımlılığını da kurar; böylece boş bir Supabase
-- projesinde migration sırası public.omehr_user_access yok diye kırılmaz.
create table if not exists public.omehr_user_access (
  auth_user_id uuid not null references auth.users(id) on delete cascade,
  tenant_id text not null,
  display_name text,
  email text,
  role_code text not null default 'USER',
  region_scope text[] not null default '{}'::text[],
  store_scope text[] not null default '{}'::text[],
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (auth_user_id, tenant_id)
);

alter table public.omehr_user_access
  add column if not exists active boolean not null default true;

alter table public.omehr_user_access enable row level security;
revoke all on table public.omehr_user_access from anon;
grant select on table public.omehr_user_access to authenticated;

drop policy if exists "users read own access" on public.omehr_user_access;
create policy "users read own access" on public.omehr_user_access
for select to authenticated
using ((select auth.uid()) = auth_user_id and active);

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
