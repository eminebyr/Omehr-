'use client'

import { FormEvent, useEffect, useMemo, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase, supabaseConfigured } from '@/lib/supabase'

type KpiRow = {
  active_current: number | null
  total_norm: number | null
  norm_deficit: number | null
  norm_surplus: number | null
  net_need: number | null
  engine_version: string | null
  calculated_at: string | null
}

type StoreRow = {
  store_id: string | null
  region_name: string | null
  store_name: string | null
  active_current: number | null
  total_norm: number | null
  norm_deficit: number | null
  norm_surplus: number | null
  calculated_at: string | null
}

type AccessRow = {
  tenant_id: string
  display_name: string | null
  email: string | null
  role_code: string | null
  region_scope: string[] | null
  store_scope: string[] | null
}

type TitleRow = {
  title_name: string
  active_current: number | null
  total_norm: number | null
  norm_deficit: number | null
  norm_surplus: number | null
  calculated_at: string | null
}

type ModulePayload = { title?: string; description?: string; rows?: Record<string, unknown>[] }
type ModuleRow = { module_key: string; payload: ModulePayload; calculated_at: string | null }

type SalesTargetRow = {
  period: string
  store_id: string
  store_name: string
  sales_target: number
  explanation: string | null
  action_plan: string | null
  owner_name: string | null
  updated_at: string
}

type PageKey =
  | 'Genel Özet'
  | 'CEO Özeti'
  | 'Bölge & Mağaza'
  | 'Personel Kartları'
  | 'Unvan Analizi'
  | 'Personel Performansı'
  | 'İş Gücü Tahmini'
  | 'Transfer Optimizasyonu'
  | 'Transfer Merkezi'
  | 'Onaylar'
  | 'AI Operasyon & Verimlilik'
  | 'Operasyon Görselleri'
  | 'Verimlilik Görselleri'
  | 'Satış Hesap Verme'
  | 'Raporlar'
  | 'Şubelere Toplu Mail'
  | 'Bildirimler'
  | 'AI Geri Bildirim'
  | 'Veri Toplama'
  | 'Ana Veri Yönetimi'
  | 'Tüm Sayfalar (Veritabanı)'
  | 'Ayarlar'

const pages: PageKey[] = [
  'Genel Özet', 'CEO Özeti', 'Bölge & Mağaza', 'Personel Kartları', 'Unvan Analizi',
  'Personel Performansı', 'İş Gücü Tahmini', 'Transfer Optimizasyonu',
  'Transfer Merkezi', 'Onaylar',
  'AI Operasyon & Verimlilik', 'Operasyon Görselleri', 'Verimlilik Görselleri',
  'Satış Hesap Verme',
  'Raporlar', 'Şubelere Toplu Mail', 'Bildirimler', 'AI Geri Bildirim', 'Veri Toplama',
  'Ana Veri Yönetimi', 'Tüm Sayfalar (Veritabanı)', 'Ayarlar',
]

const pageMeta: Record<PageKey, { subtitle: string; source: string }> = {
  'Genel Özet': { subtitle: 'Şirket geneli canlı norm ve iş gücü görünümü', source: 'omehr_kpi_snapshot + omehr_store_summary' },
  'CEO Özeti': { subtitle: 'Üst yönetim için sadeleştirilmiş karar ekranı', source: 'omehr_kpi_snapshot + omehr_engine_runs' },
  'Bölge & Mağaza': { subtitle: 'Bölge ve mağaza bazında mevcut, norm, eksik ve fazla', source: 'omehr_store_summary' },
  'Personel Kartları': { subtitle: 'Yetki kapsamında personel görünümü', source: 'omehr_personnel_*' },
  'Unvan Analizi': { subtitle: 'Unvan bazlı norm ve mevcut dengesi', source: 'omehr_title_summary' },
  'Personel Performansı': { subtitle: 'İK yetkili performans görünümü', source: 'omehr_person_performance_snapshot' },
  'İş Gücü Tahmini': { subtitle: 'Talep ve iş gücü tahmin sonuçları', source: 'omehr_workforce_forecast' },
  'Transfer Optimizasyonu': { subtitle: 'Transfer önerileri ve rota görünümü', source: 'omehr_transfer_requests + omehr_transfer_routes' },
  'Transfer Merkezi': { subtitle: 'Transfer talebi, takip ve karar akışı', source: 'Railway transfer iş akışı' },
  'Onaylar': { subtitle: 'Bölge ve İK onay merkezi', source: 'Railway onay iş akışı' },
  'AI Operasyon & Verimlilik': { subtitle: 'AI norm ve operasyon önerileri', source: 'omehr_ai_norm_recommendations' },
  'Operasyon Görselleri': { subtitle: 'Operasyon metriklerinin görsel özeti', source: 'omehr_daily_operations + omehr_hourly_density' },
  'Verimlilik Görselleri': { subtitle: 'Mağaza ve dönem verimlilik analizi', source: 'omehr_monthly_store_metrics + omehr_period_metrics' },
  'Satış Hesap Verme': { subtitle: 'Norm karşılama ve satış hedef gerçekleşme karşılaştırması', source: 'omehr_store_summary + Aylık Operasyon KPI + omehr_sales_targets' },
  'Raporlar': { subtitle: 'Yönetici ve bölge rapor merkezi', source: 'omehr_report_jobs + ileride Storage' },
  'Şubelere Toplu Mail': { subtitle: 'Yetkili toplu iletişim merkezi', source: 'omehr_mail_jobs + omehr_recipient_directory' },
  'Bildirimler': { subtitle: 'Kullanıcı ve operasyon bildirimleri', source: 'omehr_notifications' },
  'AI Geri Bildirim': { subtitle: 'AI önerilerine insan geri bildirimi', source: 'AI norm sonuçları + karar kaydı' },
  'Veri Toplama': { subtitle: 'Atanmış veri toplama formları', source: 'omehr_form_assignments + omehr_data_collection_submissions' },
  'Ana Veri Yönetimi': { subtitle: 'Kontrollü referans ve iş kuralı yönetimi', source: 'omehr_referential_control' },
  'Tüm Sayfalar (Veritabanı)': { subtitle: 'Motor veri sayfalarının denetimli görünümü', source: 'Railway modül snapshotları' },
  'Ayarlar': { subtitle: 'Kullanıcı, rol ve görünüm ayarları', source: 'omehr_user_access' },
}

function fmtDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('tr-TR', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Istanbul',
  }).format(new Date(value))
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return '—'
  if (typeof value === 'boolean') return value ? 'Evet' : 'Hayır'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function asNumber(value: unknown) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  const normalized = String(value ?? '').replace(/\./g, '').replace(',', '.')
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function money(value: number) {
  return new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(value)
}

function percent(value: number | null) {
  return value === null ? '—' : `%${new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1 }).format(value)}`
}

function ModuleTable({ payload }: { payload?: ModulePayload }) {
  const [query, setQuery] = useState('')
  const rows = payload?.rows ?? []
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('tr-TR')
    if (!needle) return rows
    return rows.filter((row) => Object.values(row).some((value) => displayValue(value).toLocaleLowerCase('tr-TR').includes(needle)))
  }, [query, rows])
  const columns = useMemo(() => {
    const names: string[] = []
    filtered.slice(0, 100).forEach((row) => Object.keys(row).forEach((key) => { if (!names.includes(key)) names.push(key) }))
    return names
  }, [filtered])
  if (!rows.length) return <div className="empty">Bu modül için Railway çıktısı henüz oluşmadı. İlgili motor veya rapor çalıştırıldığında burada görünecek.</div>
  return <section className="section module-data">
    <div className="section-title"><div><h2>{payload?.title || 'Canlı sonuçlar'}</h2>{payload?.description && <p>{payload.description}</p>}</div><div className="status-pill">{filtered.length} / {rows.length} kayıt</div></div>
    <input className="table-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Bu tabloda ara…" />
    <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{filtered.slice(0, 500).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{displayValue(row[column])}</td>)}</tr>)}</tbody></table></div>
    {filtered.length > 500 && <div className="table-limit">İlk 500 kayıt gösteriliyor. Arama ile sonucu daraltabilirsiniz.</div>}
  </section>
}

function SalesTargetForm({ access, stores, latestPeriod, onSaved }: {
  access: AccessRow | null
  stores: StoreRow[]
  latestPeriod: string
  onSaved: (row: SalesTargetRow) => void
}) {
  const role = (access?.role_code ?? '').toLocaleUpperCase('tr-TR')
  const canWrite = ['ADMIN', 'SATIS_DIREKTORU', 'SATIŞ_DİREKTÖRÜ', 'SALES_DIRECTOR'].includes(role)
  const [period, setPeriod] = useState(latestPeriod)
  const [storeId, setStoreId] = useState('')
  const [target, setTarget] = useState('')
  const [explanation, setExplanation] = useState('')
  const [actionPlan, setActionPlan] = useState('')
  const [ownerName, setOwnerName] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => { if (!period && latestPeriod) setPeriod(latestPeriod) }, [latestPeriod, period])
  if (!canWrite) return <div className="accountability-note">Satış hedefi, gerekçe ve aksiyon alanları yalnız Satış Direktörü veya yönetici rolü tarafından girilir. İK ekranı sonuçları görüntüler; manuel eşleştirme yapmaz.</div>

  async function saveTarget(event: FormEvent) {
    event.preventDefault()
    const store = stores.find((item) => String(item.store_id ?? item.store_name) === storeId)
    if (!access || !store || !period || asNumber(target) <= 0) { setMessage('Dönem, mağaza ve geçerli satış hedefi zorunludur.'); return }
    setSaving(true); setMessage('')
    const row = {
      tenant_id: access.tenant_id,
      period,
      store_id: storeId,
      store_name: store.store_name || storeId,
      sales_target: asNumber(target),
      explanation: explanation.trim() || null,
      action_plan: actionPlan.trim() || null,
      owner_name: ownerName.trim() || access.display_name || null,
      updated_at: new Date().toISOString(),
    }
    const { data, error } = await supabase.from('omehr_sales_targets').upsert(row, { onConflict: 'tenant_id,period,store_id' }).select('period,store_id,store_name,sales_target,explanation,action_plan,owner_name,updated_at').single()
    setSaving(false)
    if (error) { setMessage(`Kayıt yapılamadı: ${error.message}`); return }
    onSaved(data as SalesTargetRow); setMessage('Satış hedefi ve açıklaması kaydedildi.')
  }

  return <section className="section target-entry"><div className="section-title"><div><h2>Satış hedefi ve hesap verme girişi</h2><p>Bu alan Satış tarafından doldurulur; gerçekleşen ciro sistemden alınır.</p></div></div><form className="target-form" onSubmit={saveTarget}><label>Dönem<input value={period} onChange={(event) => setPeriod(event.target.value)} placeholder="2026-09" required /></label><label>Mağaza<select value={storeId} onChange={(event) => setStoreId(event.target.value)} required><option value="">Mağaza seçin</option>{stores.map((store) => { const id = String(store.store_id ?? store.store_name ?? ''); return <option key={id} value={id}>{store.store_name || id}</option> })}</select></label><label>Satış hedefi (TL)<input inputMode="decimal" value={target} onChange={(event) => setTarget(event.target.value)} required /></label><label>Sorumlu<input value={ownerName} onChange={(event) => setOwnerName(event.target.value)} /></label><label className="wide">Hedef sapma açıklaması<textarea value={explanation} onChange={(event) => setExplanation(event.target.value)} /></label><label className="wide">Aksiyon planı<textarea value={actionPlan} onChange={(event) => setActionPlan(event.target.value)} /></label><button className="primary form-submit" disabled={saving}>{saving ? 'Kaydediliyor…' : 'Satış hesabını kaydet'}</button></form>{message && <div className="engine-message">{message}</div>}</section>
}

export default function HomePage() {
  const [session, setSession] = useState<Session | null>(null)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [kpi, setKpi] = useState<KpiRow | null>(null)
  const [stores, setStores] = useState<StoreRow[]>([])
  const [titles, setTitles] = useState<TitleRow[]>([])
  const [modules, setModules] = useState<Record<string, ModulePayload>>({})
  const [salesTargets, setSalesTargets] = useState<SalesTargetRow[]>([])
  const [access, setAccess] = useState<AccessRow | null>(null)
  const [activePage, setActivePage] = useState<PageKey>('Genel Özet')
  const [navOpen, setNavOpen] = useState(false)
  const [engineRunning, setEngineRunning] = useState(false)
  const [engineMessage, setEngineMessage] = useState('')

  useEffect(() => {
    if (!supabaseConfigured) { setLoading(false); return }
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setLoading(false) })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession))
    return () => listener.subscription.unsubscribe()
  }, [])

  useEffect(() => {
    if (!session) return
    const userId = session.user.id
    async function loadDashboard() {
      setLoading(true); setError('')
      const accessRes = await supabase.from('omehr_user_access')
        .select('tenant_id,display_name,email,role_code,region_scope,store_scope')
        .eq('auth_user_id', userId).maybeSingle()
      if (accessRes.error || !accessRes.data?.tenant_id) {
        setAccess(null)
        setError(accessRes.error?.message || 'Kullanıcı için aktif kiracı erişimi bulunamadı.')
        setLoading(false)
        return
      }
      setAccess(accessRes.data)
      const tenantId = accessRes.data.tenant_id
      const [kpiRes, storeRes, titleRes, moduleRes, salesTargetRes] = await Promise.all([
        supabase.from('omehr_kpi_snapshot')
          .select('active_current,total_norm,norm_deficit,norm_surplus,net_need,engine_version,calculated_at')
          .eq('tenant_id', tenantId)
          .order('calculated_at', { ascending: false }).limit(1).maybeSingle(),
        supabase.from('omehr_store_summary')
          .select('store_id,region_name,store_name,active_current,total_norm,norm_deficit,norm_surplus,calculated_at')
          .eq('tenant_id', tenantId)
          .order('norm_deficit', { ascending: false }).limit(200),
        supabase.from('omehr_title_summary')
          .select('title_name,active_current,total_norm,norm_deficit,norm_surplus,calculated_at')
          .eq('tenant_id', tenantId)
          .order('norm_deficit', { ascending: false }).limit(100),
        supabase.from('omehr_module_snapshots')
          .select('module_key,payload,calculated_at')
          .eq('tenant_id', tenantId),
        supabase.from('omehr_sales_targets')
          .select('period,store_id,store_name,sales_target,explanation,action_plan,owner_name,updated_at')
          .eq('tenant_id', tenantId)
          .order('period', { ascending: false }),
      ])
      if (kpiRes.error) setError(kpiRes.error.message); else setKpi(kpiRes.data)
      if (!storeRes.error) setStores(storeRes.data ?? [])
      if (!titleRes.error) setTitles(titleRes.data ?? [])
      if (!moduleRes.error) {
        const mapped = Object.fromEntries(((moduleRes.data ?? []) as ModuleRow[]).map((row) => [row.module_key, row.payload]))
        setModules(mapped)
      }
      if (!salesTargetRes.error) setSalesTargets((salesTargetRes.data ?? []) as SalesTargetRow[])
      setLoading(false)
    }
    loadDashboard()
  }, [session])

  const netLabel = useMemo(() => {
    const value = kpi?.net_need ?? 0
    if (value < 0) return `${Math.abs(value)} kişi eksik`
    if (value > 0) return `${value} kişi fazla`
    return 'Dengede'
  }, [kpi])

  async function signIn(event: FormEvent) {
    event.preventDefault(); setError('')
    const { error: signInError } = await supabase.auth.signInWithPassword({ email, password })
    if (signInError) setError('Giriş yapılamadı. E-posta ve parolanızı kontrol edin.')
  }

  async function runEngine() {
    if (!session) return
    setEngineRunning(true); setEngineMessage('Railway norm motoru çalıştırılıyor…'); setError('')
    try {
      const response = await fetch('/api/engine/run', {
        method: 'POST',
        headers: { Authorization: `Bearer ${session.access_token}` },
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(result.error || 'Motor çalıştırılamadı.')
      const run = result.run
      const calculatedAt = new Date().toISOString()
      if (run?.kpis) {
        setKpi({
          active_current: Number(run.kpis.aktif_mevcut ?? 0),
          total_norm: Number(run.kpis.toplam_norm ?? 0),
          norm_deficit: Number(run.kpis.norm_eksigi ?? 0),
          norm_surplus: Number(run.kpis.norm_fazlasi ?? 0),
          net_need: Number(run.kpis.net_ihtiyac ?? 0),
          engine_version: 'Railway canlı motor',
          calculated_at: calculatedAt,
        })
      }
      if (Array.isArray(run?.magaza_bazli)) {
        setStores(run.magaza_bazli.map((row: Record<string, unknown>, index: number) => ({
          store_id: String(row.magaza ?? index),
          region_name: String(row.bolge_sorumlusu ?? ''),
          store_name: String(row.magaza ?? ''),
          active_current: Number(row.mevcut ?? 0),
          total_norm: Number(row.norm ?? 0),
          norm_deficit: Number(row.eksik ?? 0),
          norm_surplus: Number(row.fazla ?? 0),
          calculated_at: calculatedAt,
        })))
      }
      if (Array.isArray(run?.unvan_bazli)) {
        setTitles(run.unvan_bazli.map((row: Record<string, unknown>) => ({
          title_name: String(row.unvan ?? ''),
          active_current: Number(row.mevcut ?? 0),
          total_norm: Number(row.norm ?? 0),
          norm_deficit: Number(row.eksik ?? 0),
          norm_surplus: Number(row.fazla ?? 0),
          calculated_at: calculatedAt,
        })))
      }
      if (run?.modules && typeof run.modules === 'object') {
        setModules(run.modules as Record<string, ModulePayload>)
      }
      setEngineMessage('Motor tamamlandı; güncel Railway sonuçları ekrana yüklendi.')
    } catch (runError) {
      setEngineMessage('')
      setError(runError instanceof Error ? runError.message : 'Motor çalıştırılamadı.')
    } finally {
      setEngineRunning(false)
    }
  }

  if (!supabaseConfigured) {
    return <main className="login-shell"><section className="login-brand"><div className="eyebrow">OMEHR • Yönetim Platformu</div><h1>Doğru kadro. Güvenilir karar.</h1><p>Profesyonel Vercel arayüzü hazır. Supabase bağlantısı bekleniyor.</p></section><section className="login-panel"><div className="login-card"><h2>Bağlantı bekleniyor</h2><p>Supabase bağlantı ayarları bu deployment için tanımlı değil.</p></div></section></main>
  }

  if (!session) {
    return (
      <main className="login-shell">
        <section className="login-brand"><div className="eyebrow">OMEHR • İş Gücü Optimizasyonu</div><h1>Doğru kadro. Güvenilir karar.</h1><p>Norm kadro, mağaza dengesi, transfer, iş gücü tahmini ve yönetim analitiğini tek güvenli ekranda izleyin.</p></section>
        <section className="login-panel"><form className="login-card" onSubmit={signIn}><h2>Hesabınıza giriş yapın</h2><p>Yetkili kullanıcı hesabınızla devam edin.</p><div className="field"><label>E-posta</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required /></div><div className="field"><label>Parola</label><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required /></div><button className="primary" type="submit">Giriş yap</button>{error && <div className="error">{error}</div>}<div className="note">Erişim Supabase Auth ve RLS politikaları ile korunur.</div></form></section>
      </main>
    )
  }

  const renderKpis = () => (
    <section className="grid">
      <div className="card"><div className="metric-label">Aktif Mevcut</div><div className="metric-value">{kpi?.active_current ?? '—'}</div></div>
      <div className="card"><div className="metric-label">Toplam Norm</div><div className="metric-value">{kpi?.total_norm ?? '—'}</div></div>
      <div className="card"><div className="metric-label">Norm Eksiği</div><div className="metric-value bad">{kpi?.norm_deficit ?? '—'}</div></div>
      <div className="card"><div className="metric-label">Norm Fazlası</div><div className="metric-value good">{kpi?.norm_surplus ?? '—'}</div></div>
      <div className="card"><div className="metric-label">Net İhtiyaç</div><div className="metric-value warn">{kpi ? netLabel : '—'}</div></div>
    </section>
  )

  const renderStoreTable = () => (
    <section className="section">
      <div className="section-title"><h2>Mağaza bazlı norm görünümü</h2><div className="status-pill">{stores.length} kayıt</div></div>
      <div className="table-wrap">{loading ? <div className="empty">Veriler yükleniyor…</div> : stores.length ? <table><thead><tr><th>Bölge</th><th>Mağaza</th><th>Mevcut</th><th>Norm</th><th>Eksik</th><th>Fazla</th><th>Son Hesaplama</th></tr></thead><tbody>{stores.map((row, index) => <tr key={`${row.store_id || row.store_name}-${index}`}><td>{row.region_name || '—'}</td><td>{row.store_name || row.store_id || '—'}</td><td>{row.active_current ?? '—'}</td><td>{row.total_norm ?? '—'}</td><td>{row.norm_deficit ?? '—'}</td><td>{row.norm_surplus ?? '—'}</td><td>{fmtDate(row.calculated_at)}</td></tr>)}</tbody></table> : <div className="empty">Henüz mağaza özeti bulunamadı. Railway motoru güncel sonuçları Supabase'e yazdığında bu alan otomatik dolacak.</div>}</div>
    </section>
  )

  const renderTitleTable = () => (
    <section className="section">
      <div className="section-title"><h2>Ünvan bazlı norm görünümü</h2><div className="status-pill">{titles.length} ünvan</div></div>
      <div className="table-wrap">{loading ? <div className="empty">Veriler yükleniyor…</div> : titles.length ? <table><thead><tr><th>Ünvan</th><th>Mevcut</th><th>Norm</th><th>Eksik</th><th>Fazla</th><th>Net Fark</th><th>Son Hesaplama</th></tr></thead><tbody>{titles.map((row) => <tr key={row.title_name}><td>{row.title_name}</td><td>{row.active_current ?? '—'}</td><td>{row.total_norm ?? '—'}</td><td>{row.norm_deficit ?? '—'}</td><td>{row.norm_surplus ?? '—'}</td><td>{(row.norm_surplus ?? 0) - (row.norm_deficit ?? 0)}</td><td>{fmtDate(row.calculated_at)}</td></tr>)}</tbody></table> : <div className="empty">Henüz ünvan özeti bulunamadı. Verileri güncellediğinizde Railway motoru bu alanı kalıcı olarak dolduracak.</div>}</div>
    </section>
  )

  const renderSalesAccountability = () => {
    const operationRows = modules.operations?.rows ?? []
    const periods = operationRows.map((row) => String(row.Ay ?? row.Dönem ?? row.Donem ?? '')).filter(Boolean).sort()
    const latestPeriod = periods.at(-1) ?? salesTargets[0]?.period ?? ''
    const actualByStore = new Map<string, number>()
    operationRows.filter((row) => String(row.Ay ?? row.Dönem ?? row.Donem ?? '') === latestPeriod).forEach((row) => {
      const key = String(row.MagazaID ?? row['MağazaID'] ?? row.Mağaza ?? '').trim()
      actualByStore.set(key, asNumber(row['Aylık Ciro'] ?? row.Ciro))
    })
    const firstPeriod = periods.at(0) ?? ''
    const firstActualByStore = new Map<string, number>()
    operationRows.filter((row) => String(row.Ay ?? row.Dönem ?? row.Donem ?? '') === firstPeriod).forEach((row) => {
      const key = String(row.MagazaID ?? row['MağazaID'] ?? row.Mağaza ?? '').trim()
      firstActualByStore.set(key, asNumber(row['Aylık Ciro'] ?? row.Ciro))
    })
    const targetByStore = new Map(salesTargets.filter((row) => row.period === latestPeriod).map((row) => [row.store_id, row]))
    return <>
      <section className="accountability-intro">
        <div><span>İK göstergesi</span><strong>Norm Karşılama %</strong><small>Aktif mevcut / toplam norm</small></div>
        <div><span>Satış göstergesi</span><strong>Hedef Gerçekleşme %</strong><small>Gerçekleşen ciro / satış hedefi</small></div>
        <div><span>İncelenen dönem</span><strong>{latestPeriod || 'Veri bekleniyor'}</strong><small>Reel büyüme baz oranı: %32,11</small></div>
      </section>
      <section className="section">
        <div className="section-title"><div><h2>Karşılıklı performans tablosu</h2><p>İK ve Satış aynı mağaza ve aynı dönem için kendi göstergeleriyle değerlendirilir.</p></div><div className="status-pill">{stores.length} mağaza</div></div>
        <div className="table-wrap">{stores.length ? <table><thead><tr><th>Mağaza</th><th>Norm</th><th>Mevcut</th><th>Norm Karşılama %</th><th>Satış Hedefi</th><th>Gerçekleşen Ciro</th><th>Hedef Gerçekleşme %</th><th>Reel Büyüme %</th><th>Sapma</th><th>Satış Açıklaması / Aksiyon</th></tr></thead><tbody>{stores.map((store, index) => {
          const storeKey = String(store.store_id ?? store.store_name ?? '').trim()
          const target = targetByStore.get(storeKey)
          const actual = actualByStore.get(storeKey) ?? actualByStore.get(String(store.store_name ?? '').trim()) ?? 0
          const firstActual = firstActualByStore.get(storeKey) ?? firstActualByStore.get(String(store.store_name ?? '').trim()) ?? 0
          const normRate = (store.total_norm ?? 0) > 0 ? ((store.active_current ?? 0) / (store.total_norm ?? 1)) * 100 : null
          const salesRate = target && target.sales_target > 0 ? (actual / target.sales_target) * 100 : null
          const nominalGrowth = firstActual > 0 ? (actual / firstActual) - 1 : null
          const realGrowth = nominalGrowth === null ? null : (((1 + nominalGrowth) / 1.3211) - 1) * 100
          return <tr key={`${storeKey}-${index}`}><td>{store.store_name || store.store_id || '—'}</td><td>{store.total_norm ?? '—'}</td><td>{store.active_current ?? '—'}</td><td><strong>{percent(normRate)}</strong></td><td>{target ? money(target.sales_target) : 'Satış girişi bekleniyor'}</td><td>{actual ? money(actual) : '—'}</td><td><strong className={salesRate !== null && salesRate >= 100 ? 'good-text' : 'bad-text'}>{percent(salesRate)}</strong></td><td><strong className={realGrowth !== null && realGrowth >= 0 ? 'good-text' : 'bad-text'}>{percent(realGrowth)}</strong></td><td>{target ? money(actual - target.sales_target) : '—'}</td><td>{target ? <>{target.explanation || 'Açıklama yok'}{target.action_plan && <small className="cell-note">Aksiyon: {target.action_plan}</small>}</> : 'Satış açıklaması bekleniyor'}</td></tr>
        })}</tbody></table> : <div className="empty">Mağaza norm sonuçları bekleniyor.</div>}</div>
      </section>
      <SalesTargetForm access={access} stores={stores} latestPeriod={latestPeriod} onSaved={(row) => setSalesTargets((current) => [row, ...current.filter((item) => !(item.period === row.period && item.store_id === row.store_id))])} />
    </>
  }

  const renderPage = () => {
    if (activePage === 'Genel Özet') return <>{renderKpis()}{renderStoreTable()}</>
    if (activePage === 'CEO Özeti') return <><section className="executive-grid"><div className="executive-card"><span>İş Gücü Dengesi</span><strong>{kpi ? netLabel : '—'}</strong><small>Şirket geneli net norm görünümü</small></div><div className="executive-card"><span>Son Motor</span><strong>{kpi?.engine_version || '—'}</strong><small>{fmtDate(kpi?.calculated_at ?? null)}</small></div><div className="executive-card"><span>Mağaza Kapsamı</span><strong>{stores.length || '—'}</strong><small>Supabase'de görünen mağaza özetleri</small></div></section>{renderKpis()}<ModuleTable payload={modules.forecast_summary} /></>
    if (activePage === 'Bölge & Mağaza') return renderStoreTable()
    if (activePage === 'Unvan Analizi') return <>{renderTitleTable()}<ModuleTable payload={modules.store_title} /></>
    if (activePage === 'Personel Kartları') return <ModuleTable payload={modules.personnel} />
    if (activePage === 'Personel Performansı') return <ModuleTable payload={modules.performance} />
    if (activePage === 'İş Gücü Tahmini') return <><ModuleTable payload={modules.forecast_summary} /><ModuleTable payload={modules.forecast} /></>
    if (activePage === 'Transfer Optimizasyonu') return <ModuleTable payload={modules.transfer} />
    if (activePage === 'AI Operasyon & Verimlilik') return <><ModuleTable payload={modules.ai_norm} /><ModuleTable payload={modules.model_comparison} /></>
    if (activePage === 'Operasyon Görselleri') return <><ModuleTable payload={modules.operations} /><ModuleTable payload={modules.hourly_density} /></>
    if (activePage === 'Verimlilik Görselleri') return <><ModuleTable payload={modules.productivity} /><ModuleTable payload={modules.overtime} /><ModuleTable payload={modules.absence} /></>
    if (activePage === 'Satış Hesap Verme') return renderSalesAccountability()
    if (activePage === 'Raporlar') return <ModuleTable payload={modules.reports} />
    if (activePage === 'Tüm Sayfalar (Veritabanı)') return <>{Object.entries(modules).map(([key, payload]) => <ModuleTable key={key} payload={payload} />)}</>
    const operational = ['Transfer Merkezi', 'Onaylar', 'Şubelere Toplu Mail', 'Bildirimler', 'AI Geri Bildirim', 'Veri Toplama', 'Ana Veri Yönetimi', 'Ayarlar'].includes(activePage)
    return <section className="module-card"><div className="module-icon">OMEHR</div><div><h2>{activePage}</h2><p>{pageMeta[activePage].subtitle}</p><div className="module-source">Veri kaynağı: {pageMeta[activePage].source}</div><div className="module-note">{operational ? 'Bu ekran kayıt veya onay işlemi yapar. Streamlit ile aynı yetki, belge ve bildirim kuralları güvenli API üzerinden bağlanıyor; salt-okunur veri ekranlarından ayrı doğrulanacaktır.' : 'Bu modül için henüz yayımlanmış Railway sonucu bulunmuyor.'}</div></div></section>
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand"><button className="menu-button" onClick={() => setNavOpen(!navOpen)}>☰</button><div className="brand-mark">O</div><div><div className="brand-title">OMEHR</div><div className="brand-sub">İş Gücü Optimizasyon Platformu</div></div></div>
        <div className="userbox"><span>{access?.display_name || session.user.email}</span><span>•</span><span>{access?.role_code || 'Yetkili Kullanıcı'}</span><button className="ghost engine-button" onClick={runEngine} disabled={engineRunning}>{engineRunning ? 'Motor çalışıyor…' : 'Verileri güncelle'}</button><button className="ghost" onClick={() => supabase.auth.signOut()}>Çıkış</button></div>
      </header>

      <div className="app-frame">
        <aside className={`sidebar ${navOpen ? 'open' : ''}`}>
          <div className="sidebar-label">YÖNETİM MENÜSÜ</div>
          <nav>{pages.map((page) => <button key={page} className={`nav-item ${activePage === page ? 'active' : ''}`} onClick={() => { setActivePage(page); setNavOpen(false) }}>{page}</button>)}</nav>
          <div className="sidebar-foot"><span className="live-dot" /> Supabase bağlantısı aktif</div>
        </aside>

        <div className="container main-content">
          <section className="hero"><div><div className="eyebrow">{activePage}</div><h1>{pageMeta[activePage].subtitle}</h1><p className="lead">Yetkiniz dahilindeki OMEHR verileri Supabase üzerinden güvenli biçimde görüntülenir.</p></div><div className="status-pill">Son veri: {fmtDate(kpi?.calculated_at ?? null)} · {kpi?.engine_version || 'motor bilgisi bekleniyor'}</div></section>
          {renderPage()}
          {engineMessage && <div className="engine-message">{engineMessage}</div>}
          {error && <div className="error">İşlem uyarısı: {error}</div>}
        </div>
      </div>
    </main>
  )
}
