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

type PageKey =
  | 'Genel Özet'
  | 'CEO Özeti'
  | 'Bölge & Mağaza'
  | 'Personel Kartları'
  | 'Unvan Analizi'
  | 'Personel Performansı'
  | 'İş Gücü Tahmini'
  | 'Transfer Optimizasyonu'
  | 'AI Operasyon & Verimlilik'
  | 'Operasyon Görselleri'
  | 'Verimlilik Görselleri'
  | 'Raporlar'
  | 'Şubelere Toplu Mail'
  | 'Bildirimler'
  | 'Veri Toplama'
  | 'Ana Veri Yönetimi'
  | 'Ayarlar'

const pages: PageKey[] = [
  'Genel Özet', 'CEO Özeti', 'Bölge & Mağaza', 'Personel Kartları', 'Unvan Analizi',
  'Personel Performansı', 'İş Gücü Tahmini', 'Transfer Optimizasyonu',
  'AI Operasyon & Verimlilik', 'Operasyon Görselleri', 'Verimlilik Görselleri',
  'Raporlar', 'Şubelere Toplu Mail', 'Bildirimler', 'Veri Toplama', 'Ana Veri Yönetimi', 'Ayarlar',
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
  'AI Operasyon & Verimlilik': { subtitle: 'AI norm ve operasyon önerileri', source: 'omehr_ai_norm_recommendations' },
  'Operasyon Görselleri': { subtitle: 'Operasyon metriklerinin görsel özeti', source: 'omehr_daily_operations + omehr_hourly_density' },
  'Verimlilik Görselleri': { subtitle: 'Mağaza ve dönem verimlilik analizi', source: 'omehr_monthly_store_metrics + omehr_period_metrics' },
  'Raporlar': { subtitle: 'Yönetici ve bölge rapor merkezi', source: 'omehr_report_jobs + ileride Storage' },
  'Şubelere Toplu Mail': { subtitle: 'Yetkili toplu iletişim merkezi', source: 'omehr_mail_jobs + omehr_recipient_directory' },
  'Bildirimler': { subtitle: 'Kullanıcı ve operasyon bildirimleri', source: 'omehr_notifications' },
  'Veri Toplama': { subtitle: 'Atanmış veri toplama formları', source: 'omehr_form_assignments + omehr_data_collection_submissions' },
  'Ana Veri Yönetimi': { subtitle: 'Kontrollü referans ve iş kuralı yönetimi', source: 'omehr_referential_control' },
  'Ayarlar': { subtitle: 'Kullanıcı, rol ve görünüm ayarları', source: 'omehr_user_access' },
}

function fmtDate(value: string | null) {
  if (!value) return '—'
  return new Intl.DateTimeFormat('tr-TR', {
    dateStyle: 'medium', timeStyle: 'short', timeZone: 'Europe/Istanbul',
  }).format(new Date(value))
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
      const [kpiRes, storeRes, titleRes] = await Promise.all([
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
      ])
      if (kpiRes.error) setError(kpiRes.error.message); else setKpi(kpiRes.data)
      if (!storeRes.error) setStores(storeRes.data ?? [])
      if (!titleRes.error) setTitles(titleRes.data ?? [])
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

  const renderPage = () => {
    if (activePage === 'Genel Özet') return <>{renderKpis()}{renderStoreTable()}</>
    if (activePage === 'CEO Özeti') return <><section className="executive-grid"><div className="executive-card"><span>İş Gücü Dengesi</span><strong>{kpi ? netLabel : '—'}</strong><small>Şirket geneli net norm görünümü</small></div><div className="executive-card"><span>Son Motor</span><strong>{kpi?.engine_version || '—'}</strong><small>{fmtDate(kpi?.calculated_at ?? null)}</small></div><div className="executive-card"><span>Mağaza Kapsamı</span><strong>{stores.length || '—'}</strong><small>Supabase'de görünen mağaza özetleri</small></div></section>{renderKpis()}</>
    if (activePage === 'Bölge & Mağaza') return renderStoreTable()
    if (activePage === 'Unvan Analizi') return renderTitleTable()
    return <section className="module-card"><div className="module-icon">OMEHR</div><div><h2>{activePage}</h2><p>{pageMeta[activePage].subtitle}</p><div className="module-source">Veri kaynağı: {pageMeta[activePage].source}</div><div className="module-note">Arayüz modülü hazır. İlgili Supabase tablosu güncel Railway sonuçlarıyla beslendiğinde bu ekran canlı veriye geçecek.</div></div></section>
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
