'use client'

// Streamlit'in web/tab_modules/genel_ozet.py dosyasındaki "Norm Eksiği Isı
// Haritası", "Norm Fazlası Isı Haritası" ve "Mağaza Risk Ağaç Haritası"
// (px.imshow / px.treemap) grafiklerinin React karşılığı.
//
// Isı haritaları için harici bir kütüphane KULLANILMIYOR — recharts'ın
// yerleşik bir heatmap bileşeni yok, ve Bölge×Unvan gibi düzenli bir
// tablo yapısı için renkli hücreli bir <table> zaten en sade ve en
// güvenilir çözüm (ekstra bağımlılık, ekstra risk yok).
//
// Treemap için recharts'ın kendi <Treemap> bileşeni kullanılıyor; varsayılan
// içerik render'ı yalın kutular çizdiği için özel bir hücre bileşeni
// (TreemapCell) ile Streamlit'teki gibi etiket + değer gösteriliyor.
//
// Veri kaynağı: bu bileşenler API çağrısı YAPMAZ — mevcut sayfa state'inden
// (omehr_module_snapshots'taki 'store_title' modülünün satırları ve
// omehr_store_summary'den gelen `stores`) prop olarak veri alır. Bu, sayfa
// zaten yaptığı Supabase sorgularını tekrarlamamak içindir.

import { useMemo } from 'react'
import {
  Treemap, ResponsiveContainer, Tooltip, BarChart, Bar, XAxis, YAxis, CartesianGrid, Legend,
  ScatterChart, Scatter, ZAxis,
} from 'recharts'

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

// omehr_module_snapshots'taki 'store_title' modülünün ham satırı —
// Türkçe anahtarlar korunuyor (services/cloud_module_snapshots.py'nin
// ürettiği DataFrame kolon adlarıyla birebir aynı).
type StoreTitleRow = Record<string, unknown>

function toNumber(value: unknown): number {
  const n = Number(value)
  return Number.isFinite(n) ? n : 0
}

function buildPivot(rows: StoreTitleRow[], valueKey: 'Eksik' | 'Fazla') {
  const regions = new Set<string>()
  const titles = new Set<string>()
  const sums = new Map<string, number>()
  for (const row of rows) {
    const region = String(row['Bölge Sorumlusu'] ?? '').trim()
    const title = String(row['Unvan'] ?? '').trim()
    if (!region || !title) continue
    const value = toNumber(row[valueKey])
    regions.add(region)
    titles.add(title)
    const key = `${region}__${title}`
    sums.set(key, (sums.get(key) ?? 0) + value)
  }
  // Streamlit'teki "tamamen sıfır olan unvan sütununu at" davranışıyla
  // aynı: hiçbir bölgede değeri olmayan unvan sütunları listeden çıkar.
  const activeTitles = [...titles].filter((title) => {
    for (const region of regions) {
      if ((sums.get(`${region}__${title}`) ?? 0) !== 0) return true
    }
    return false
  })
  return {
    regions: [...regions].sort(),
    titles: activeTitles.sort(),
    get: (region: string, title: string) => sums.get(`${region}__${title}`) ?? 0,
  }
}

function deficitColor(intensity: number): string {
  if (intensity <= 0) return 'transparent'
  const lightness = 78 - intensity * 48
  return `hsl(357, 62%, ${lightness}%)`
}

function surplusColor(intensity: number): string {
  if (intensity <= 0) return 'transparent'
  const lightness = 78 - intensity * 48
  return `hsl(37, 74%, ${lightness}%)`
}

function HeatmapGrid({
  title, rows, valueKey, colorScale,
}: {
  title: string
  rows: StoreTitleRow[]
  valueKey: 'Eksik' | 'Fazla'
  colorScale: (intensity: number) => string
}) {
  const pivot = useMemo(() => buildPivot(rows, valueKey), [rows, valueKey])
  if (pivot.regions.length === 0 || pivot.titles.length === 0) {
    return (
      <div className="heatmap-wrap">
        <h3>{title}</h3>
        <div className="empty">Bu görsel için yeterli veri yok.</div>
      </div>
    )
  }
  let max = 0
  for (const region of pivot.regions) {
    for (const t of pivot.titles) max = Math.max(max, pivot.get(region, t))
  }
  return (
    <div className="heatmap-wrap">
      <h3>{title}</h3>
      <div className="heatmap-scroll">
        <table className="heatmap-table">
          <thead>
            <tr>
              <th className="heatmap-corner">Bölge Sorumlusu \ Unvan</th>
              {pivot.titles.map((t) => <th key={t}>{t}</th>)}
            </tr>
          </thead>
          <tbody>
            {pivot.regions.map((region) => (
              <tr key={region}>
                <th>{region}</th>
                {pivot.titles.map((t) => {
                  const value = pivot.get(region, t)
                  const intensity = max > 0 ? value / max : 0
                  return (
                    <td key={t} style={{ background: colorScale(intensity) }}>
                      {value !== 0 ? value : ''}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function NormEksigiIsiHaritasi({ rows }: { rows: StoreTitleRow[] }) {
  return <HeatmapGrid title="Norm Eksiği Isı Haritası" rows={rows} valueKey="Eksik" colorScale={deficitColor} />
}

export function NormFazlasiIsiHaritasi({ rows }: { rows: StoreTitleRow[] }) {
  return <HeatmapGrid title="Norm Fazlası Isı Haritası" rows={rows} valueKey="Fazla" colorScale={surplusColor} />
}

// --- Gauge (Plotly go.Indicator karşılığı) -------------------------------
// recharts'ta hazır bir "gauge" bileşeni yok; Plotly'nin renkli dilimli
// (steps) + eşik çizgili (threshold) yarım-daire göstergesini birebir
// üretmek için düz SVG ile çiziliyor — ekstra bağımlılık gerekmiyor.

function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
  const angleRad = ((angleDeg - 180) * Math.PI) / 180
  return { x: cx + r * Math.cos(angleRad), y: cy + r * Math.sin(angleRad) }
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(cx, cy, r, endAngle)
  const end = polarToCartesian(cx, cy, r, startAngle)
  const largeArc = endAngle - startAngle <= 180 ? '0' : '1'
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`
}

type GaugeStep = { from: number; to: number; color: string }

export function GaugeChart({
  title, subtitle, value, max, steps, barColor, thresholdValue,
}: {
  title: string
  subtitle?: string
  value: number
  max: number
  steps: GaugeStep[]
  barColor: string
  thresholdValue?: number
}) {
  const safeMax = max > 0 ? max : 100
  const clamped = Math.max(0, Math.min(value, safeMax))
  const cx = 150
  const cy = 120
  const outerR = 108
  const innerR = 82
  const valueAngle = (clamped / safeMax) * 180
  const thresholdAngle = thresholdValue != null ? (Math.min(thresholdValue, safeMax) / safeMax) * 180 : null

  return (
    <div className="gauge-wrap">
      <svg viewBox="0 0 300 150" className="gauge-svg">
        {/* Dış halka: renkli zemin dilimleri (Plotly'nin "steps" karşılığı) — DÜZELTME:
            önceki sürümde bunlar değer çubuğuyla AYNI yarıçapta çiziliyor ve çok koyu
            renkler kullanılıyordu, koyu panel zeminiyle karışıp neredeyse görünmez
            oluyordu. Artık ayrı (dış) halka + belirgin renk tonları kullanılıyor. */}
        {steps.map((step, i) => (
          <path
            key={i}
            d={describeArc(cx, cy, outerR, (step.from / safeMax) * 180, (step.to / safeMax) * 180)}
            stroke={step.color} strokeWidth={16} fill="none"
          />
        ))}
        {/* İç halka: gerçek değer çubuğu — dış halkadan ayrı, karışmıyor */}
        <path d={describeArc(cx, cy, innerR, 0, 180)} stroke="var(--panel-2)" strokeWidth={14} fill="none" />
        <path d={describeArc(cx, cy, innerR, 0, valueAngle)} stroke={barColor} strokeWidth={14} fill="none" strokeLinecap="round" />
        {thresholdAngle != null && (() => {
          const p1 = polarToCartesian(cx, cy, innerR - 14, thresholdAngle)
          const p2 = polarToCartesian(cx, cy, outerR + 14, thresholdAngle)
          return <line x1={p1.x} y1={p1.y} x2={p2.x} y2={p2.y} stroke="var(--danger)" strokeWidth={3} />
        })()}
        <text x={cx} y={cy - 8} textAnchor="middle" fontSize={28} fontWeight={800} fill="var(--text)">
          {clamped.toFixed(1)}%
        </text>
      </svg>
      <div className="gauge-caption">
        <strong>{title}</strong>
        {subtitle && <span>{subtitle}</span>}
      </div>
    </div>
  )
}

export function BrutVeDagilimGosterge({
  active, totalNorm, deficit,
}: { active: number; totalNorm: number; deficit: number }) {
  const brutOran = totalNorm ? (active / totalNorm) * 100 : 0
  const dagilimKarsilanan = Math.max(0, totalNorm - deficit)
  const dagilimOran = totalNorm ? (dagilimKarsilanan / totalNorm) * 100 : 0
  const steps: GaugeStep[] = [
    { from: 0, to: 90, color: '#c0546b' },
    { from: 90, to: 100, color: '#c9a34a' },
    { from: 100, to: 110, color: '#4f9e6e' },
  ]
  return (
    <div className="grid-2">
      <GaugeChart title="Brüt Karşılama" subtitle={`${active} / ${totalNorm}`} value={brutOran} max={110} steps={steps} barColor="#4472C4" thresholdValue={100} />
      <GaugeChart title="Dağılım Bazlı Karşılama" subtitle={`${dagilimKarsilanan} / ${totalNorm}`} value={dagilimOran} max={110} steps={steps} barColor="#70AD47" thresholdValue={100} />
    </div>
  )
}

export function NormKarsilamaOraniGosterge({ active, totalNorm }: { active: number; totalNorm: number }) {
  const coverage = totalNorm ? (active / totalNorm) * 100 : 0
  const max = Math.max(110, Math.ceil(coverage / 10) * 10)
  const steps: GaugeStep[] = [
    { from: 0, to: 100, color: '#3f6fb0' },
    { from: 100, to: max, color: '#c0546b' },
  ]
  return <GaugeChart title="Norm Karşılama Oranı" value={coverage} max={max} steps={steps} barColor="#4472C4" thresholdValue={100} />
}

// --- Bar & Scatter (recharts) ---------------------------------------------

function regionTotals(stores: StoreRow[]) {
  const map = new Map<string, { region: string; Eksik: number; Fazla: number }>()
  for (const s of stores) {
    const region = (s.region_name ?? '').trim() || 'Bilinmiyor'
    const entry = map.get(region) ?? { region, Eksik: 0, Fazla: 0 }
    entry.Eksik += toNumber(s.norm_deficit)
    entry.Fazla += toNumber(s.norm_surplus)
    map.set(region, entry)
  }
  return [...map.values()]
}

export function BolgeBazliEksikFazlaGrafigi({ stores }: { stores: StoreRow[] }) {
  const data = useMemo(() => regionTotals(stores), [stores])
  if (data.length === 0) return <div className="chart-wrap"><div className="empty">Veri yok.</div></div>
  return (
    <div className="chart-wrap">
      <h3>Bölge Bazlı Norm Eksiği / Fazlası</h3>
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
          <XAxis dataKey="region" angle={-30} textAnchor="end" interval={0} height={80} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <YAxis tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--text)' }} />
          <Legend />
          <Bar dataKey="Eksik" fill="var(--danger)" />
          <Bar dataKey="Fazla" fill="var(--success)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function UnvanBazliEnYuksekAciklarGrafigi({ titles }: { titles: { title_name: string; norm_deficit: number | null }[] }) {
  const data = useMemo(() => {
    return [...titles]
      .map((t) => ({ Unvan: t.title_name, Eksik: toNumber(t.norm_deficit) }))
      .filter((row) => row.Eksik > 0)
      .sort((a, b) => b.Eksik - a.Eksik)
      .slice(0, 20)
  }, [titles])
  if (data.length === 0) return <div className="chart-wrap"><div className="empty">Veri yok.</div></div>
  return (
    <div className="chart-wrap">
      <h3>Unvan Bazlı En Yüksek Açıklar</h3>
      <ResponsiveContainer width="100%" height={Math.max(320, data.length * 28)}>
        <BarChart data={data} layout="vertical" margin={{ top: 10, right: 30, left: 40, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
          <XAxis type="number" tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <YAxis type="category" dataKey="Unvan" width={160} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--text)' }} />
          <Bar dataKey="Eksik" fill="var(--gold)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export function MevcutNormSacilimGrafigi({ stores }: { stores: StoreRow[] }) {
  const data = useMemo(() => stores.map((s) => ({
    Norm: toNumber(s.total_norm),
    Mevcut: toNumber(s.active_current),
    Eksik: toNumber(s.norm_deficit),
    Magaza: s.store_name ?? '—',
    Bolge: s.region_name ?? '—',
  })), [stores])
  if (data.length === 0) return <div className="chart-wrap"><div className="empty">Veri yok.</div></div>
  return (
    <div className="chart-wrap">
      <h3>Mevcut - Norm Saçılımı</h3>
      <ResponsiveContainer width="100%" height={380}>
        <ScatterChart margin={{ top: 10, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
          <XAxis type="number" dataKey="Norm" name="Norm" tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <YAxis type="number" dataKey="Mevcut" name="Mevcut" tick={{ fill: 'var(--muted)', fontSize: 11 }} />
          <ZAxis type="number" dataKey="Eksik" range={[40, 400]} name="Eksik" />
          <Tooltip
            cursor={{ strokeDasharray: '3 3' }}
            contentStyle={{ background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--text)' }}
            formatter={(value, name) => [`${value}`, name]}
            labelFormatter={() => ''}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as { Magaza: string; Bolge: string; Norm: number; Mevcut: number; Eksik: number }
              return (
                <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', padding: 8, borderRadius: 8 }}>
                  <div><strong>{p.Magaza}</strong> ({p.Bolge})</div>
                  <div>Norm: {p.Norm} · Mevcut: {p.Mevcut} · Eksik: {p.Eksik}</div>
                </div>
              )
            }}
          />
          <Scatter data={data} fill="var(--teal)" />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}

type TreemapLeaf = { name: string; size: number }
type TreemapBranch = { name: string; children: TreemapLeaf[] }

function TreemapCell(props: unknown) {
  const { x, y, width, height, name, size, depth } = props as {
    x: number; y: number; width: number; height: number; name: string; size: number; depth: number
  }
  if (width < 2 || height < 2) return null
  const fill = depth === 1 ? 'var(--navy)' : 'var(--teal)'
  const showLabel = width > 46 && height > 22
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} style={{ fill, stroke: 'var(--bg)', strokeWidth: 1 }} />
      {showLabel && (
        <text x={x + 6} y={y + 17} fill="#fff" fontSize={12} fontWeight={600}>{name}</text>
      )}
      {showLabel && depth !== 1 && (
        <text x={x + 6} y={y + 32} fill="#e5e7eb" fontSize={11}>Norm Eksiği: {size}</text>
      )}
    </g>
  )
}

export function MagazaRiskAgacHaritasi({ stores }: { stores: StoreRow[] }) {
  const data = useMemo<TreemapBranch[]>(() => {
    const byRegion = new Map<string, TreemapLeaf[]>()
    for (const s of stores) {
      const deficit = toNumber(s.norm_deficit)
      if (deficit <= 0) continue
      const region = (s.region_name ?? '').trim() || 'Bilinmiyor'
      const store = (s.store_name ?? '').trim() || 'Bilinmiyor'
      const list = byRegion.get(region) ?? []
      list.push({ name: store, size: deficit })
      byRegion.set(region, list)
    }
    return [...byRegion.entries()].map(([region, leaves]) => ({ name: region, children: leaves }))
  }, [stores])

  if (data.length === 0) {
    return (
      <div className="treemap-wrap">
        <h3>Mağaza Risk Ağaç Haritası</h3>
        <div className="empty">Risk haritası için norm eksiği olan mağaza bulunamadı.</div>
      </div>
    )
  }

  return (
    <div className="treemap-wrap">
      <h3>Mağaza Risk Ağaç Haritası</h3>
      <ResponsiveContainer width="100%" height={420}>
        <Treemap data={data} dataKey="size" nameKey="name" stroke="var(--bg)" content={<TreemapCell />}>
          <Tooltip formatter={(value) => [`${value ?? 0}`, 'Norm Eksiği']} />
        </Treemap>
      </ResponsiveContainer>
    </div>
  )
}
