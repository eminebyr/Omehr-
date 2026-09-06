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
import { Treemap, ResponsiveContainer, Tooltip } from 'recharts'

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
