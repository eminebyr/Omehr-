'use client'

import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

type Row = Record<string, unknown>
type Payload = { rows?: Row[]; status?: string; status_message?: string }

const tr = new Intl.NumberFormat('tr-TR', { maximumFractionDigits: 1 })
const money = new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 })

function num(value: unknown) {
  if (typeof value === 'number') return Number.isFinite(value) ? value : 0
  const raw = String(value ?? '').trim()
  if (!raw) return 0
  const normalized = raw.includes(',') ? raw.replace(/\./g, '').replace(',', '.') : raw
  const parsed = Number(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function text(row: Row, ...keys: string[]) {
  for (const key of keys) {
    const value = String(row[key] ?? '').trim()
    if (value && value !== 'nan') return value
  }
  return ''
}

function sumBy(rows: Row[], labelKeys: string[], valueKey: string, limit = 20) {
  const grouped = new Map<string, number>()
  for (const row of rows) {
    const label = text(row, ...labelKeys)
    if (!label) continue
    grouped.set(label, (grouped.get(label) ?? 0) + num(row[valueKey]))
  }
  return [...grouped].map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value).slice(0, limit)
}

function averageBy(rows: Row[], labelKeys: string[], valueKey: string, limit = 20) {
  const grouped = new Map<string, { total: number; count: number }>()
  for (const row of rows) {
    const label = text(row, ...labelKeys)
    if (!label) continue
    const current = grouped.get(label) ?? { total: 0, count: 0 }
    current.total += num(row[valueKey]); current.count += 1
    grouped.set(label, current)
  }
  return [...grouped].map(([name, item]) => ({ name, value: item.count ? item.total / item.count : 0 }))
    .sort((a, b) => b.value - a.value).slice(0, limit)
}

function Empty({ payload, label }: { payload?: Payload; label: string }) {
  return <div className="empty">{payload?.status_message || `${label} verisi Railway tarafından henüz üretilmedi.`}</div>
}

function Kpis({ items }: { items: { label: string; value: string; note?: string }[] }) {
  return <section className="accountability-intro">{items.map((item) => <div key={item.label}>
    <span>{item.label}</span><strong>{item.value}</strong>{item.note && <small>{item.note}</small>}
  </div>)}</section>
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return <article className="chart-card"><h3>{title}</h3><div style={{ width: '100%', height: 380 }}>{children}</div></article>
}

function HorizontalBars({ data, color = '#16b8c4', suffix = '' }: { data: { name: string; value: number }[]; color?: string; suffix?: string }) {
  return <ResponsiveContainer width="100%" height="100%"><BarChart data={data} layout="vertical" margin={{ left: 36, right: 34, top: 8, bottom: 8 }}>
    <CartesianGrid strokeDasharray="3 3" stroke="#173451" /><XAxis type="number" tick={{ fill: '#a9bfd8' }} />
    <YAxis dataKey="name" type="category" width={130} tick={{ fill: '#a9bfd8', fontSize: 11 }} />
    <Tooltip formatter={(value) => `${tr.format(Number(value))}${suffix}`} /><Bar dataKey="value" fill={color} radius={[0, 7, 7, 0]} />
  </BarChart></ResponsiveContainer>
}

export function WorkforceForecastPanel({ detail, summary, validation, staffingValidation, turnoverValidation }: {
  detail?: Payload; summary?: Payload; validation?: Payload; staffingValidation?: Payload; turnoverValidation?: Payload
}) {
  const rows = detail?.rows ?? []
  const [horizon, setHorizon] = useState(30)
  const [stores, setStores] = useState<string[]>([])
  const [titles, setTitles] = useState<string[]>([])
  const horizonRows = useMemo(() => rows.filter((row) => num(row['Tahmin Ufku Gün']) === horizon), [rows, horizon])
  const storeOptions = useMemo(() => [...new Set(horizonRows.map((row) => text(row, 'Mağaza', 'Magaza')).filter(Boolean))].sort(), [horizonRows])
  const titleOptions = useMemo(() => [...new Set(horizonRows.map((row) => text(row, 'Unvan', 'Ünvan')).filter(Boolean))].sort(), [horizonRows])
  const view = horizonRows.filter((row) => (!stores.length || stores.includes(text(row, 'Mağaza', 'Magaza'))) && (!titles.length || titles.includes(text(row, 'Unvan', 'Ünvan'))))
  const summaryRow = (summary?.rows ?? []).find((row) => num(row['Tahmin Ufku Gün']) === horizon)
  const staffing = sumBy(view, ['Mağaza', 'Magaza'], 'Tahmini Açık/Fazla')
  const observed = view.filter((row) => ['Yüksek', 'Orta', 'Düşük'].includes(text(row, 'Turnover Veri Durumu')))
  const turnover = sumBy(observed, ['Mağaza', 'Magaza'], 'Turnover Riski FTE')

  if (!rows.length) return <Empty payload={detail} label="İş gücü tahmini" />
  const toggle = (value: string, selected: string[], setSelected: (next: string[]) => void) => setSelected(selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value])
  const filterPanel = <section className="section"><div className="section-title"><div><h2>30 / 60 / 90 Günlük İş Gücü Tahmini</h2><p>Railway tahmin motorunun mağaza ve unvan bazlı güncel sonuçları.</p></div></div>
    <div className="filter-chips">{[30, 60, 90].map((value) => <button className={horizon === value ? 'active' : ''} key={value} onClick={() => setHorizon(value)}>{value} gün</button>)}</div>
    <div className="parity-filters"><label>Mağaza filtresi<select value="" onChange={(event) => event.target.value && toggle(event.target.value, stores, setStores)}><option value="">Mağaza seçin</option>{storeOptions.filter((item) => !stores.includes(item)).map((item) => <option key={item}>{item}</option>)}</select><span className="selected-chips">{stores.length ? stores.map((item) => <button key={item} onClick={() => toggle(item, stores, setStores)} title="Filtreyi kaldır">{item} ×</button>) : <small>Tümü</small>}</span></label>
    <label>Unvan filtresi<select value="" onChange={(event) => event.target.value && toggle(event.target.value, titles, setTitles)}><option value="">Unvan seçin</option>{titleOptions.filter((item) => !titles.includes(item)).map((item) => <option key={item}>{item}</option>)}</select><span className="selected-chips">{titles.length ? titles.map((item) => <button key={item} onClick={() => toggle(item, titles, setTitles)} title="Filtreyi kaldır">{item} ×</button>) : <small>Tümü</small>}</span></label></div>
  </section>
  if (!horizonRows.length) return <>{filterPanel}<div className="engine-message">{horizon} günlük tahmin verisi henüz Railway motoru tarafından oluşturulmadı. Başka bir tahmin ufku seçebilirsiniz.</div></>
  return <>
    {filterPanel}
    <Kpis items={[
      { label: 'Ham Tahmin Adayı', value: tr.format(num(summaryRow?.['Tahmini Gerekli Kadro'])) },
      { label: 'Aktif Mevcut', value: tr.format(num(summaryRow?.['Aktif Mevcut'])) },
      { label: 'Tahmini Açık', value: tr.format(num(summaryRow?.['Toplam Tahmini Açık'])) },
      { label: 'Tahmini Fazla', value: tr.format(num(summaryRow?.['Toplam Tahmini Fazla'])) },
      { label: 'Ortalama Güven', value: `%${tr.format(num(summaryRow?.['Ortalama Güven %']))}` },
    ]} />
    <div className="chart-grid"><ChartCard title={`${horizon} Günlük Mağaza Bazında Tahmini Açık / Fazla`}><HorizontalBars data={staffing} color="#4472c4" /></ChartCard>
    <ChartCard title={`${horizon} Günlük Mağaza Bazında Turnover Riski (FTE)`}>{turnover.length ? <HorizontalBars data={turnover} color="#d64545" /> : <Empty label="Gözleme dayalı turnover riski" />}</ChartCard></div>
    <section className="section"><div className="section-title"><div><h2>Açıklanabilir tahmin ayrıntısı</h2><p>{view.length} mağaza–unvan tahmini; filtrelerle birlikte canlı değişir.</p></div></div><SimpleTable rows={view} /></section>
    <section className="section"><div className="section-title"><div><h2>Tahmin doğrulaması</h2><p>Operasyon, kadro ve turnover tahminlerinin Railway backtest sonuçları.</p></div></div>
      <SimpleTable rows={(validation?.rows ?? []).filter((row) => !row['Tahmin Ufku Gün'] || num(row['Tahmin Ufku Gün']) === horizon)} />
      <h3 style={{ marginTop: 24 }}>Mağaza–unvan kadro doğruluğu</h3><SimpleTable rows={(staffingValidation?.rows ?? []).filter((row) => !row['Tahmin Ufku Gün'] || num(row['Tahmin Ufku Gün']) === horizon)} />
      <h3 style={{ marginTop: 24 }}>Turnover oranı tahmin doğruluğu</h3><SimpleTable rows={(turnoverValidation?.rows ?? []).filter((row) => !row['Tahmin Ufku Gün'] || num(row['Tahmin Ufku Gün']) === horizon)} /></section>
  </>
}

export function OperationsPanel({ monthly, daily, hourly, register, inflation }: { monthly?: Payload; daily?: Payload; hourly?: Payload; register?: Payload; inflation?: Payload }) {
  const dailyRows = daily?.rows ?? []
  const monthlyRows = monthly?.rows ?? []
  const registerRows = register?.rows ?? []
  const dailyTrend = useMemo(() => {
    const grouped = new Map<string, { date: string; revenue: number; tickets: number }>()
    for (const row of dailyRows) { const date = text(row, 'Tarih'); if (!date) continue; const item = grouped.get(date) ?? { date, revenue: 0, tickets: 0 }; item.revenue += num(row.Ciro); item.tickets += num(row['Fiş Adedi']); grouped.set(date, item) }
    return [...grouped.values()].sort((a, b) => a.date.localeCompare(b.date, 'tr'))
  }, [dailyRows])
  const topRevenue = sumBy(dailyRows, ['Mağaza', 'Magaza'], 'Ciro', 15)
  const registerUse = averageBy(registerRows, ['Mağaza', 'Magaza'], 'Kullanım Oranı %', 20)
  const periodInflationRate = num((inflation?.rows ?? [])[0]?.['Dönem Enflasyonu %'] ?? (inflation?.rows ?? [])[0]?.['Enflasyon %'] ?? (inflation?.rows ?? [])[0]?.['Yıllık Enflasyon %'] ?? 32.11)
  const monthlyPeriods = useMemo(() => [...new Set(monthlyRows.map((row) => text(row, 'Ay', 'Dönem')).filter(Boolean))].sort(), [monthlyRows])
  // Railway değeri karşılaştırılan dönemin kümülatif enflasyonudur
  // (ör. Ocak–Haziran 2026: %32,11); gelecek aylar kullanılarak yıllıklaştırılmaz.
  const periodInflationFactor = 1 + periodInflationRate / 100
  const realGrowth = useMemo(() => {
    if (monthlyPeriods.length < 2) return []
    const first = monthlyPeriods[0], last = monthlyPeriods[monthlyPeriods.length - 1]
    const firstMap = new Map(monthlyRows.filter((r) => text(r, 'Ay', 'Dönem') === first).map((r) => [text(r, 'Mağaza', 'Magaza'), num(r['Aylık Ciro'])]))
    return monthlyRows.filter((r) => text(r, 'Ay', 'Dönem') === last).map((r) => { const name = text(r, 'Mağaza', 'Magaza'); const base = firstMap.get(name) ?? 0; const nominal = base ? num(r['Aylık Ciro']) / base : 0; return { name, value: base ? ((nominal / periodInflationFactor) - 1) * 100 : 0 } }).filter((r) => r.name).sort((a, b) => b.value - a.value)
  }, [monthlyRows, monthlyPeriods, periodInflationFactor])
  const heatRows = hourly?.rows ?? []
  const heatStores = [...new Set(heatRows.map((row) => text(row, 'Mağaza', 'Magaza')).filter(Boolean))].slice(0, 10)
  const heatHours = [...new Set(heatRows.map((row) => text(row, 'Saat')).filter(Boolean))].sort((a, b) => num(a) - num(b))
  const heatMax = Math.max(...heatRows.map((row) => num(row['Yoğunluk Skoru'])), 1)
  const heatIndex = useMemo(() => {
    const index = new Map<string, { sum: number; count: number }>()
    for (const row of heatRows) {
      const store = text(row, 'Mağaza', 'Magaza'), hour = text(row, 'Saat')
      if (!store || !hour) continue
      const key = `${store}\u0000${hour}`, current = index.get(key) ?? { sum: 0, count: 0 }
      current.sum += num(row['Yoğunluk Skoru']); current.count += 1; index.set(key, current)
    }
    return index
  }, [heatRows])
  if (!dailyRows.length && !monthlyRows.length) return <Empty payload={daily} label="Operasyon" />
  return <>
    <Kpis items={[
      { label: 'Dönem Toplam Ciro', value: money.format(dailyRows.reduce((sum, row) => sum + num(row.Ciro), 0)) },
      { label: 'Dönem Toplam Fiş', value: tr.format(dailyRows.reduce((sum, row) => sum + num(row['Fiş Adedi']), 0)) },
      { label: 'Ortalama Kasa Kullanımı', value: `%${tr.format(registerRows.length ? registerRows.reduce((sum, row) => sum + num(row['Kullanım Oranı %']), 0) / registerRows.length : 0)}` },
    ]} />
    <div className="chart-grid"><ChartCard title="Günlük Toplam Ciro Trendi"><ResponsiveContainer><LineChart data={dailyTrend}><CartesianGrid strokeDasharray="3 3" stroke="#173451" /><XAxis dataKey="date" tick={{ fill: '#a9bfd8', fontSize: 10 }} /><YAxis tick={{ fill: '#a9bfd8' }} /><Tooltip /><Line dataKey="revenue" stroke="#4472c4" strokeWidth={3} dot={false} /></LineChart></ResponsiveContainer></ChartCard>
    <ChartCard title="Günlük Toplam Fiş Adedi Trendi"><ResponsiveContainer><LineChart data={dailyTrend}><CartesianGrid strokeDasharray="3 3" stroke="#173451" /><XAxis dataKey="date" tick={{ fill: '#a9bfd8', fontSize: 10 }} /><YAxis tick={{ fill: '#a9bfd8' }} /><Tooltip /><Line dataKey="tickets" stroke="#118b94" strokeWidth={3} dot={false} /></LineChart></ResponsiveContainer></ChartCard></div>
    <div className="chart-grid"><ChartCard title="En Yüksek Ciro Yapan 15 Mağaza"><HorizontalBars data={topRevenue} color="#4472c4" /></ChartCard><ChartCard title="Ortalama Kasa Kullanım Oranı (%)"><HorizontalBars data={registerUse} color="#118b94" suffix="%" /></ChartCard></div>
    <section className="section"><div className="section-title"><div><h2>Saatlik Yoğunluk Skoru</h2><p>İlk 10 mağaza × saat; renk koyulaştıkça yoğunluk yükselir.</p></div></div>{heatRows.length ? <div className="heatmap"><div />{heatHours.map((hour) => <b key={hour}>{hour}</b>)}{heatStores.flatMap((store) => [<strong key={`${store}-name`}>{store}</strong>, ...heatHours.map((hour) => { const item = heatIndex.get(`${store}\u0000${hour}`); const value = item?.count ? item.sum / item.count : 0; return <i key={`${store}-${hour}`} title={`${store} · ${hour}: ${tr.format(value)}`} style={{ background: `rgba(214,69,69,${Math.max(.08, value / heatMax)})` }}>{tr.format(value)}</i> })])}</div> : <Empty payload={hourly} label="Saatlik yoğunluk" />}</section>
    <ChartCard title={`Mağaza Bazında Reel Büyüme — dönem enflasyonu %${tr.format(periodInflationRate)}`}><ResponsiveContainer><BarChart data={realGrowth} layout="vertical" margin={{ left: 36, right: 30 }}><CartesianGrid strokeDasharray="3 3" stroke="#173451" /><XAxis type="number" tick={{ fill: '#a9bfd8' }} /><YAxis type="category" dataKey="name" width={130} tick={{ fill: '#a9bfd8', fontSize: 11 }} /><Tooltip formatter={(v) => `%${tr.format(Number(v))}`} /><Bar dataKey="value">{realGrowth.map((item) => <Cell key={item.name} fill={item.value >= 0 ? '#70ad47' : '#c00000'} />)}</Bar></BarChart></ResponsiveContainer></ChartCard>
  </>
}

export function ProductivityPanel({ workload, personnelCost, overtime, turnoverRisk, absence }: { workload?: Payload; personnelCost?: Payload; overtime?: Payload; turnoverRisk?: Payload; absence?: Payload }) {
  const workloadRows = workload?.rows ?? []
  const costRows = personnelCost?.rows ?? []
  const overtimeRows = overtime?.rows ?? []
  const absenceRows = absence?.rows ?? []
  const latest = (rows: Row[]) => {
    const periods = [...new Set(rows.map((r) => text(r, 'Ay', 'Dönem')).filter(Boolean))].sort()
    return periods[periods.length - 1] ?? ''
  }
  const lastCost = latest(costRows), lastOvertime = latest(overtimeRows), lastAbsence = latest(absenceRows)
  const costTrend = sumByPeriod(costRows, 'Personel Maliyeti')
  const absenceTrend = sumByPeriod(absenceRows, 'Fiili Kayıp FTE')
  if (!workloadRows.length && !overtimeRows.length) return <Empty payload={workload} label="Verimlilik" />
  return <>
    <Kpis items={[
      { label: 'Ortalama İş Yükü Endeksi', value: tr.format(workloadRows.length ? workloadRows.reduce((s, r) => s + num(r['İş Yükü Endeksi']), 0) / workloadRows.length : 0) },
      { label: 'Son Ay Personel Maliyeti', value: money.format(costRows.filter((r) => text(r, 'Ay', 'Dönem') === lastCost).reduce((s, r) => s + num(r['Personel Maliyeti']), 0)), note: lastCost },
      { label: 'Son Ay Toplam Fazla Mesai', value: `${tr.format(overtimeRows.filter((r) => text(r, 'Ay', 'Dönem') === lastOvertime).reduce((s, r) => s + num(r['Fazla Mesai Saat']), 0))} sa`, note: lastOvertime },
      { label: 'Son Ay Devamsızlık Kaybı', value: `${tr.format(absenceRows.filter((r) => text(r, 'Ay', 'Dönem') === lastAbsence).reduce((s, r) => s + num(r['Fiili Kayıp FTE']), 0))} FTE`, note: lastAbsence },
    ]} />
    <div className="chart-grid"><ChartCard title="Mağaza Bazında İş Yükü Endeksi"><HorizontalBars data={averageBy(workloadRows, ['Mağaza', 'Magaza'], 'İş Yükü Endeksi')} color="#118b94" /></ChartCard><ChartCard title="En Yüksek Fazla Mesai"><HorizontalBars data={sumBy(overtimeRows, ['Mağaza', 'Magaza'], 'Fazla Mesai Saat', 15)} color="#118b94" suffix=" sa" /></ChartCard></div>
    <div className="chart-grid"><ChartCard title="En Yüksek Personel Devir Riski"><HorizontalBars data={averageBy(turnoverRisk?.rows ?? [], ['Mağaza', 'Magaza'], 'Risk Skoru', 15)} color="#d64545" /></ChartCard><ChartCard title="Aylık Toplam Personel Maliyeti"><Trend data={costTrend} dataKey="value" color="#4472c4" /></ChartCard></div>
    <ChartCard title="Aylık Devamsızlıktan Kaynaklanan Fiili Kayıp (FTE)"><Trend data={absenceTrend} dataKey="value" color="#c00000" /></ChartCard>
  </>
}

function sumByPeriod(rows: Row[], valueKey: string) {
  const grouped = new Map<string, number>()
  for (const row of rows) { const period = text(row, 'Ay', 'Dönem'); if (period) grouped.set(period, (grouped.get(period) ?? 0) + num(row[valueKey])) }
  return [...grouped].sort(([a], [b]) => a.localeCompare(b)).map(([period, value]) => ({ period, value }))
}

function Trend({ data, dataKey, color }: { data: { period: string; value: number }[]; dataKey: string; color: string }) {
  return <ResponsiveContainer width="100%" height="100%"><LineChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="#173451" /><XAxis dataKey="period" tick={{ fill: '#a9bfd8' }} /><YAxis tick={{ fill: '#a9bfd8' }} /><Tooltip /><Legend /><Line dataKey={dataKey} stroke={color} strokeWidth={3} /></LineChart></ResponsiveContainer>
}

function SimpleTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return <div className="empty">Bu bölüm için henüz doğrulanabilir veri bulunmuyor.</div>
  const columns = [...new Set(rows.slice(0, 100).flatMap(Object.keys))]
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.slice(0, 500).map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{String(row[column] ?? '—')}</td>)}</tr>)}</tbody></table></div>
}
