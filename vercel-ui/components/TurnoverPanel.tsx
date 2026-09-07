'use client'

import { useMemo, useState } from 'react'
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

type PersonnelRow = Record<string, unknown>

type TurnoverRow = {
  store: string
  region: string
  entries: number
  exits: number
  active: number
  turnover: number
  earlyExits: number
}

const ENTRY_KEYS = ['İşe Giriş', 'Ise Giris', 'İşe Giriş Tarihi', 'Ise Giris Tarihi']
const EXIT_KEYS = ['İşten Çıkış', 'Isten Cikis', 'İşten Çıkış Tarihi', 'Isten Cikis Tarihi']
const STORE_KEYS = ['Mağaza', 'Magaza', 'Mağaza Adı', 'Magaza Adi']
const REGION_KEYS = ['Bölge Sorumlusu', 'Bolge Sorumlusu', 'Bölge Müdürü', 'Bolge Muduru']
const EXIT_REASON_KEYS = ['Çıkış Nedeni', 'Cikis Nedeni', 'Çıkış Kodu', 'Cikis Kodu']
const TENURE_DAY_KEYS = ['Kıdem (Gün)', 'Kidem (Gun)', 'Kıdem Gün', 'Kidem Gun']
const TITLE_KEYS = ['Gerçek Unvan', 'Gerçek Ünvan', 'Gercek Unvan', 'Unvan', 'Ünvan']

function firstValue(row: PersonnelRow, keys: string[]) {
  for (const key of keys) {
    const value = row[key]
    if (value !== null && value !== undefined && String(value).trim() !== '') return value
  }
  return null
}

function parseDate(value: unknown): Date | null {
  if (value === null || value === undefined || String(value).trim() === '') return null
  if (typeof value === 'number' && Number.isFinite(value)) {
    const date = new Date(Date.UTC(1899, 11, 30))
    date.setUTCDate(date.getUTCDate() + value)
    return date
  }
  const text = String(value).trim()
  const tr = text.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})/)
  const date = tr
    ? new Date(Number(tr[3]), Number(tr[2]) - 1, Number(tr[1]))
    : new Date(text)
  return Number.isNaN(date.getTime()) ? null : date
}

function parseOptionalNumber(value: unknown): number | null {
  if (value === null || value === undefined || String(value).trim() === '') return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const parsed = Number(String(value).trim().replace(/\./g, '').replace(',', '.'))
  return Number.isFinite(parsed) ? parsed : null
}

function isoInput(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatNumber(value: number, digits = 0) {
  return new Intl.NumberFormat('tr-TR', { maximumFractionDigits: digits }).format(value)
}

function within(date: Date | null, start: Date, end: Date) {
  return !!date && date >= start && date <= end
}

export function TurnoverPanel({ rows }: { rows: PersonnelRow[] }) {
  const today = useMemo(() => new Date(), [])
  const initialStart = useMemo(() => {
    const date = new Date(today)
    date.setFullYear(date.getFullYear() - 1)
    return isoInput(date)
  }, [today])
  const [startValue, setStartValue] = useState(initialStart)
  const [endValue, setEndValue] = useState(isoInput(today))
  const [selectedStore, setSelectedStore] = useState('')

  const result = useMemo(() => {
    const start = new Date(`${startValue}T00:00:00`)
    const end = new Date(`${endValue}T23:59:59.999`)
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || start > end) return null

    const normalized = rows.map((row) => ({
      store: String(firstValue(row, STORE_KEYS) ?? '').trim(),
      region: String(firstValue(row, REGION_KEYS) ?? 'Bilinmiyor').trim() || 'Bilinmiyor',
      entry: parseDate(firstValue(row, ENTRY_KEYS)),
      exit: parseDate(firstValue(row, EXIT_KEYS)),
      exitReason: String(firstValue(row, EXIT_REASON_KEYS) ?? 'Belirtilmemiş').trim() || 'Belirtilmemiş',
      tenureDays: parseOptionalNumber(firstValue(row, TENURE_DAY_KEYS)),
      title: String(firstValue(row, TITLE_KEYS) ?? 'Belirtilmemiş').trim() || 'Belirtilmemiş',
    })).filter((row) => row.store)

    const calculate = (items: typeof normalized): Omit<TurnoverRow, 'store' | 'region'> => {
      const entries = items.filter((row) => within(row.entry, start, end)).length
      const exits = items.filter((row) => within(row.exit, start, end)).length
      const active = items.filter((row) => (!row.entry || row.entry <= end) && (!row.exit || row.exit > end)).length
      const startHeadcount = Math.max(0, active - entries + exits)
      const averageHeadcount = (startHeadcount + active) / 2
      const earlyExits = items.filter((row) => {
        if (!within(row.exit, start, end) || !row.exit) return false
        const tenureDays = row.entry
          ? (row.exit.getTime() - row.entry.getTime()) / 86_400_000
          : row.tenureDays
        return tenureDays !== null && tenureDays >= 0 && tenureDays <= 90
      }).length
      return {
        entries,
        exits,
        active,
        turnover: averageHeadcount > 0 ? exits / averageHeadcount * 100 : 0,
        earlyExits,
      }
    }

    const stores = [...new Set(normalized.map((row) => row.store))].map((store) => {
      const storeRows = normalized.filter((row) => row.store === store)
      return {
        store,
        region: storeRows.find((row) => row.region !== 'Bilinmiyor')?.region ?? storeRows[0]?.region ?? 'Bilinmiyor',
        ...calculate(storeRows),
      }
    }).sort((a, b) => b.turnover - a.turnover || a.store.localeCompare(b.store, 'tr'))

    const regions = [...new Set(normalized.map((row) => row.region))].map((region) => ({
      region,
      ...calculate(normalized.filter((row) => row.region === region)),
    })).sort((a, b) => b.exits - a.exits || b.turnover - a.turnover)

    const totals = calculate(normalized)
    const unclassifiedEarlyExits = normalized.filter((row) => {
      if (!within(row.exit, start, end) || !row.exit) return false
      const tenureDays = row.entry
        ? (row.exit.getTime() - row.entry.getTime()) / 86_400_000
        : row.tenureDays
      return tenureDays === null || tenureDays < 0
    }).length
    const reasonCounts = new Map<string, {
      reason: string
      region: string
      store: string
      title: string
      count: number
    }>()
    for (const row of normalized) {
      if (!within(row.exit, start, end)) continue
      const key = JSON.stringify([row.exitReason, row.region, row.store, row.title])
      const current = reasonCounts.get(key)
      if (current) current.count += 1
      else reasonCounts.set(key, {
        reason: row.exitReason,
        region: row.region,
        store: row.store,
        title: row.title,
        count: 1,
      })
    }
    const exitReasons = [...reasonCounts.values()]
      .map((row) => ({
        ...row,
        label: `${row.reason} · ${row.region} · ${row.store} · ${row.title}`,
        share: totals.exits > 0 ? row.count / totals.exits * 100 : 0,
      }))
      .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason, 'tr'))

    const generalReasonCounts = new Map<string, number>()
    for (const row of exitReasons) {
      generalReasonCounts.set(row.reason, (generalReasonCounts.get(row.reason) ?? 0) + row.count)
    }
    const generalExitReasons = [...generalReasonCounts.entries()]
      .map(([reason, count]) => ({
        reason,
        count,
        share: totals.exits > 0 ? count / totals.exits * 100 : 0,
      }))
      .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason, 'tr'))

    return {
      ...totals,
      earlyShare: totals.exits > 0 ? totals.earlyExits / totals.exits * 100 : 0,
      unclassifiedEarlyExits,
      stores,
      regions,
      generalExitReasons,
      exitReasons,
    }
  }, [rows, startValue, endValue])

  const selected = result?.stores.find((row) => row.store === selectedStore)
  const chartRows = result?.stores.filter((row) => row.exits > 0).slice(0, 15) ?? []
  const storeExitRows = result?.stores.filter((row) => row.exits > 0).sort((a, b) => b.exits - a.exits).slice(0, 15) ?? []
  const regionExitRows = result?.regions.filter((row) => row.exits > 0) ?? []
  const hasRequiredColumns = rows.some((row) =>
    firstValue(row, ENTRY_KEYS) !== null &&
    firstValue(row, STORE_KEYS) !== null
  ) && rows.some((row) => EXIT_KEYS.some((key) => key in row))

  return <section className="section">
    <div className="section-title">
      <div>
        <h2>Turnover Analizi</h2>
        <p>Dönemsel çalışan devri ve ilk 90 gün ayrılışlarını şirket ve mağaza bazında gösterir.</p>
      </div>
      <div className="status-pill">{result?.stores.length ?? 0} mağaza</div>
    </div>

    {!hasRequiredColumns ? (
      <div className="accountability-note">
        Turnover hesaplamak için personel verisinde Mağaza, İşe Giriş ve İşten Çıkış tarihleri bulunmalıdır.
      </div>
    ) : <>
      <div className="target-form">
        <label>Dönem başlangıcı
          <input type="date" value={startValue} onChange={(event) => setStartValue(event.target.value)} />
        </label>
        <label>Dönem sonu
          <input type="date" value={endValue} onChange={(event) => setEndValue(event.target.value)} />
        </label>
        <label>Mağaza detayı
          <select value={selectedStore} onChange={(event) => setSelectedStore(event.target.value)}>
            <option value="">Mağaza seçin</option>
            {result?.stores.map((row) => <option value={row.store} key={row.store}>{row.store}</option>)}
          </select>
        </label>
      </div>

      {!result ? <div className="accountability-note">Başlangıç tarihi dönem sonundan sonra olamaz.</div> : <>
        <div className="accountability-intro section">
          <div><span>Dönemsel Turnover</span><strong>%{formatNumber(result.turnover, 1)}</strong><small>Çıkış / ortalama çalışan sayısı</small></div>
          <div><span>İlk 90 Gün Ayrılış Payı</span><strong>%{formatNumber(result.earlyShare, 1)}</strong><small>{result.earlyExits} erken ayrılış</small></div>
          <div><span>Giriş / Çıkış</span><strong>{result.entries} / {result.exits}</strong><small>Seçilen tarih aralığı</small></div>
          <div><span>Dönem Sonu Aktif</span><strong>{result.active}</strong><small>O tarihte henüz çıkışı gerçekleşmemiş personel</small></div>
        </div>

        {result.unclassifiedEarlyExits > 0 && <div className="accountability-note">
          {result.unclassifiedEarlyExits} çıkış kaydında işe giriş tarihi veya kıdem günü bulunmadığı için ilk 90 gün sınıflaması yapılamadı.
        </div>}

        {selected && <div className="executive-grid section">
          <div className="executive-card"><span>{selected.store} · Giriş / Çıkış</span><strong>{selected.entries} / {selected.exits}</strong><small>Seçilen tarih aralığı</small></div>
          <div className="executive-card"><span>Turnover</span><strong>%{formatNumber(selected.turnover, 1)}</strong><small>Mağaza bazlı çalışan devri</small></div>
          <div className="executive-card"><span>İlk 90 Gün Çıkış</span><strong>{selected.earlyExits}</strong><small>Dönem sonu aktif: {selected.active}</small></div>
        </div>}

        <div className="chart-grid section">
          <article className="chart-card">
            <h3>Bölge Müdürü Bazlı Ayrılan Personel</h3>
            {regionExitRows.length ? <ResponsiveContainer width="100%" height={Math.max(300, regionExitRows.length * 48)}>
              <BarChart data={regionExitRows} layout="vertical" margin={{ top: 10, right: 35, bottom: 10, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--muted)' }} />
                <YAxis type="category" dataKey="region" width={145} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
                <Tooltip formatter={(value) => [formatNumber(Number(value)), 'Ayrılan']} />
                <Bar dataKey="exits" fill="var(--gold)" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer> : <div className="empty">Seçilen dönemde bölge bazlı ayrılış kaydı bulunmuyor.</div>}
          </article>

          <article className="chart-card">
            <h3>Mağaza Bazlı En Fazla Ayrılış</h3>
            {storeExitRows.length ? <ResponsiveContainer width="100%" height={Math.max(360, storeExitRows.length * 32)}>
              <BarChart data={storeExitRows} layout="vertical" margin={{ top: 10, right: 35, bottom: 10, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--muted)' }} />
                <YAxis type="category" dataKey="store" width={130} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
                <Tooltip formatter={(value) => [formatNumber(Number(value)), 'Ayrılan']} />
                <Bar dataKey="exits" fill="var(--teal)" radius={[0, 6, 6, 0]} />
              </BarChart>
            </ResponsiveContainer> : <div className="empty">Seçilen dönemde mağaza bazlı ayrılış kaydı bulunmuyor.</div>}
          </article>
        </div>

        <div className="chart-card section">
          <h3>Turnover Oranı En Yüksek Mağazalar</h3>
          {chartRows.length ? <ResponsiveContainer width="100%" height={Math.max(360, chartRows.length * 32)}>
            <BarChart data={chartRows} layout="vertical" margin={{ top: 10, right: 35, bottom: 10, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis type="number" tick={{ fill: 'var(--muted)' }} unit="%" />
              <YAxis type="category" dataKey="store" width={130} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
              <Tooltip formatter={(value) => [`%${formatNumber(Number(value), 1)}`, 'Turnover']} />
              <Bar dataKey="turnover" fill="var(--danger)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer> : <div className="empty">Seçilen dönemde işten çıkış kaydı bulunmuyor.</div>}
        </div>

        <div className="table-wrap section">
          <table>
            <thead><tr><th>Mağaza</th><th>Giriş</th><th>Çıkış</th><th>Dönem Sonu Aktif</th><th>Turnover %</th><th>İlk 90 Gün Çıkış</th></tr></thead>
            <tbody>{result.stores.map((row) => <tr key={row.store}>
              <td>{row.store}</td><td>{row.entries}</td><td>{row.exits}</td><td>{row.active}</td>
              <td><strong className={row.turnover >= 10 ? 'bad-text' : ''}>%{formatNumber(row.turnover, 1)}</strong></td>
              <td>{row.earlyExits}</td>
            </tr>)}</tbody>
          </table>
        </div>

        <div className="chart-card section">
          <h3>Genel Çıkış Nedenleri</h3>
          {result.generalExitReasons.length ? <ResponsiveContainer width="100%" height={Math.max(320, result.generalExitReasons.length * 42)}>
            <BarChart data={result.generalExitReasons} layout="vertical" margin={{ top: 10, right: 35, bottom: 10, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--muted)' }} />
              <YAxis type="category" dataKey="reason" width={210} tick={{ fill: 'var(--muted)', fontSize: 11 }} />
              <Tooltip formatter={(value) => [formatNumber(Number(value)), 'Ayrılan']} />
              <Bar dataKey="count" fill="var(--gold)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer> : <div className="empty">Seçilen dönemde çıkış nedeni analizi için kayıt bulunmuyor.</div>}
        </div>

        {result.generalExitReasons.length > 0 && <div className="table-wrap section">
          <table>
            <thead><tr><th>Çıkış Nedeni</th><th>Ayrılan</th><th>Toplam Çıkış Payı</th></tr></thead>
            <tbody>{result.generalExitReasons.map((row) => <tr key={row.reason}>
              <td>{row.reason}</td><td>{row.count}</td><td>%{formatNumber(row.share, 1)}</td>
            </tr>)}</tbody>
          </table>
        </div>}

        <div className="chart-card section">
          <h3>Çıkış Nedenleri · Bölge, Mağaza ve Gerçek Unvan Kırılımı</h3>
          {result.exitReasons.length ? <ResponsiveContainer width="100%" height={Math.max(360, result.exitReasons.length * 44)}>
            <BarChart data={result.exitReasons} layout="vertical" margin={{ top: 10, right: 35, bottom: 10, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis type="number" allowDecimals={false} tick={{ fill: 'var(--muted)' }} />
              <YAxis type="category" dataKey="label" width={310} tick={{ fill: 'var(--muted)', fontSize: 10 }} />
              <Tooltip formatter={(value) => [formatNumber(Number(value)), 'Ayrılan']} />
              <Bar dataKey="count" fill="var(--gold)" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer> : <div className="empty">Seçilen dönemde çıkış nedeni analizi için kayıt bulunmuyor.</div>}
        </div>

        {result.exitReasons.length > 0 && <div className="table-wrap section">
          <table>
            <thead><tr><th>Çıkış Nedeni</th><th>Bölge Sorumlusu</th><th>Mağaza</th><th>Gerçek Unvan</th><th>Ayrılan</th><th>Toplam Çıkış Payı</th></tr></thead>
            <tbody>{result.exitReasons.map((row) => <tr key={row.label}>
              <td>{row.reason}</td><td>{row.region}</td><td>{row.store}</td><td>{row.title}</td>
              <td>{row.count}</td><td>%{formatNumber(row.share, 1)}</td>
            </tr>)}</tbody>
          </table>
        </div>}
      </>}
    </>}
  </section>
}
