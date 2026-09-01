export type DataRow = Record<string, unknown>

export type SalesEvidence = {
  period: string
  storeId: string
  storeName: string
  revenue: number | null
  tickets: number | null
  basket: number | null
  revenueChange: number | null
  ticketChange: number | null
  basketChange: number | null
  realGrowth: number | null
  overtimeHours: number | null
  absenceDays: number | null
  lostFte: number | null
  workloadIndex: number | null
  wasteRate: number | null
  managerScore: number | null
  customerExperience: number | null
  onlineOrders: number | null
  goodsReceipt: number | null
}

export type RootCauseResult = {
  code: string
  title: string
  severity: 'good' | 'watch' | 'bad' | 'missing'
  evidence: string[]
  personnelClaim: 'supported' | 'unsupported' | 'inconclusive'
  requiredAction: string
}

const numberValue = (value: unknown): number | null => {
  if (value === null || value === undefined || value === '') return null
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  const parsed = Number(String(value).replace(/\s/g, '').replace(/\./g, '').replace(',', '.'))
  return Number.isFinite(parsed) ? parsed : null
}

export const textValue = (value: unknown) => String(value ?? '').trim()
export const rowPeriod = (row: DataRow) => textValue(row.Ay ?? row.Dönem ?? row.Donem ?? row.Tarih).slice(0, 7)
export const rowStoreId = (row: DataRow) => textValue(row.MagazaID ?? row['MağazaID'] ?? row.Mağaza ?? row.Magaza)
export const rowStoreName = (row: DataRow) => textValue(row.Mağaza ?? row.Magaza ?? row.MagazaID ?? row['MağazaID'])
export const pctChange = (current: number | null, previous: number | null) => current !== null && previous !== null && previous !== 0 ? ((current / previous) - 1) * 100 : null

const byStorePeriod = (rows: DataRow[], period: string) => new Map(
  rows.filter((row) => !period || !rowPeriod(row) || rowPeriod(row) === period).map((row) => [rowStoreId(row), row]),
)

export function buildSalesEvidence(args: {
  operations: DataRow[]
  overtime: DataRow[]
  absence: DataRow[]
  productivity: DataRow[]
  wasteReturns: DataRow[]
  performance: DataRow[]
  onlineOrders: DataRow[]
  goodsReceipt: DataRow[]
  inflationPct: number
}): { latestPeriod: string; previousPeriod: string; byStore: Map<string, SalesEvidence> } {
  const periods = [...new Set(args.operations.map(rowPeriod).filter(Boolean))].sort()
  const latestPeriod = periods.at(-1) ?? ''
  const previousPeriod = periods.at(-2) ?? ''
  const current = byStorePeriod(args.operations, latestPeriod)
  const previous = byStorePeriod(args.operations, previousPeriod)
  const overtime = byStorePeriod(args.overtime, latestPeriod)
  const absence = byStorePeriod(args.absence, latestPeriod)
  const productivity = byStorePeriod(args.productivity, '')
  const waste = byStorePeriod(args.wasteReturns, latestPeriod)
  const performance = byStorePeriod(args.performance, latestPeriod)
  const online = byStorePeriod(args.onlineOrders, latestPeriod)
  const goods = byStorePeriod(args.goodsReceipt, latestPeriod)
  const result = new Map<string, SalesEvidence>()
  current.forEach((row, storeId) => {
    const prior = previous.get(storeId)
    const revenue = numberValue(row['Aylık Ciro'] ?? row.Ciro)
    const tickets = numberValue(row['Aylık Fiş'] ?? row['Fiş Adedi'])
    const basket = numberValue(row['Ort. Sepet'] ?? row['Ortalama Sepet'])
    const previousRevenue = numberValue(prior?.['Aylık Ciro'] ?? prior?.Ciro)
    const revenueChange = pctChange(revenue, previousRevenue)
    result.set(storeId, {
      period: latestPeriod, storeId, storeName: rowStoreName(row), revenue, tickets, basket,
      revenueChange,
      ticketChange: pctChange(tickets, numberValue(prior?.['Aylık Fiş'] ?? prior?.['Fiş Adedi'])),
      basketChange: pctChange(basket, numberValue(prior?.['Ort. Sepet'] ?? prior?.['Ortalama Sepet'])),
      realGrowth: revenueChange === null ? null : (((1 + revenueChange / 100) / (1 + args.inflationPct / 100)) - 1) * 100,
      overtimeHours: numberValue(overtime.get(storeId)?.['Fazla Mesai Saat']),
      absenceDays: numberValue(absence.get(storeId)?.['Devamsızlık Gün']),
      lostFte: numberValue(absence.get(storeId)?.['Fiili Kayıp FTE']),
      workloadIndex: numberValue(productivity.get(storeId)?.['İş Yükü Endeksi']),
      wasteRate: numberValue(waste.get(storeId)?.['Fire Oranı %']),
      managerScore: numberValue(performance.get(storeId)?.['Yönetici Puanı']),
      customerExperience: numberValue(performance.get(storeId)?.['Müşteri Deneyimi']),
      onlineOrders: numberValue(online.get(storeId)?.['Günlük Sipariş']),
      goodsReceipt: numberValue(goods.get(storeId)?.['Günlük Mal Kabul']),
    })
  })
  return { latestPeriod, previousPeriod, byStore: result }
}

export function diagnoseSales(args: { evidence?: SalesEvidence; normRate: number | null; salesRate: number | null }): RootCauseResult {
  const { evidence: e, normRate, salesRate } = args
  if (!e || salesRate === null) return { code: 'VERI_EKSIK', title: 'Analiz için hedef veya gerçekleşen veri eksik', severity: 'missing', evidence: [], personnelClaim: 'inconclusive', requiredAction: 'Satış hedefi ve dönem verisini tamamla.' }
  if (salesRate >= 100 && (normRate ?? 100) < 95) return { code: 'EKSIK_KADROYLA_HEDEF_USTU', title: 'Eksik kadroyla hedef aşıldı', severity: 'watch', evidence: [`Hedef gerçekleşme ${salesRate.toFixed(1)}%`, `Norm karşılama ${(normRate ?? 0).toFixed(1)}%`], personnelClaim: 'unsupported', requiredAction: 'Sürdürülebilirlik, fazla mesai ve çalışan yükünü incele.' }
  if (salesRate >= 100) return { code: 'HEDEF_TUTTU', title: 'Satış hedefi gerçekleşti', severity: 'good', evidence: [`Hedef gerçekleşme ${salesRate.toFixed(1)}%`], personnelClaim: 'unsupported', requiredAction: 'Sonucu koru; fire ve iş yükü guardrail’lerini izle.' }

  const evidence: string[] = [`Hedef gerçekleşme ${salesRate.toFixed(1)}%`]
  if (e.ticketChange !== null) evidence.push(`Fiş değişimi ${e.ticketChange.toFixed(1)}%`)
  if (e.basketChange !== null) evidence.push(`Sepet değişimi ${e.basketChange.toFixed(1)}%`)
  if (e.realGrowth !== null) evidence.push(`Reel büyüme ${e.realGrowth.toFixed(1)}%`)
  if (e.wasteRate !== null) evidence.push(`Fire ${e.wasteRate.toFixed(1)}%`)
  if ((normRate ?? 100) >= 98) return { code: 'TAM_KADRO_DUSUK_SATIS', title: 'Norm dolu; satış sapması kadroyla açıklanamaz', severity: 'bad', evidence, personnelClaim: 'unsupported', requiredAction: 'Fiş, sepet, stok/fire, kategori ve mağaza yönetimi aksiyonu iste.' }
  if ((e.ticketChange ?? 0) < -3 && (e.basketChange ?? 0) >= -3) return { code: 'MUSTERI_TRAFIGI', title: 'Ana sinyal: fiş/müşteri trafiği düşüşü', severity: 'bad', evidence, personnelClaim: 'unsupported', requiredAction: 'Trafik, kampanya, rekabet ve mağaza çekiciliği kök nedenini açıkla.' }
  if ((e.basketChange ?? 0) < -3) return { code: 'SEPET_DUSUSU', title: 'Ana sinyal: ortalama sepet düşüşü', severity: 'bad', evidence, personnelClaim: 'unsupported', requiredAction: 'Ürün karması, fiyat, kampanya ve stok bulunurluğunu açıkla.' }
  const peopleEvidence = (normRate ?? 100) < 95 && ((e.overtimeHours ?? 0) > 0 || (e.lostFte ?? 0) > 0 || (e.workloadIndex ?? 0) >= 70)
  if (peopleEvidence) return { code: 'PERSONEL_ETKISI_KANITLI', title: 'Personel etkisi veriyle destekleniyor', severity: 'bad', evidence, personnelClaim: 'supported', requiredAction: 'Eksik unvan/saat ile satış kaybı bağlantısını ve telafi planını kaydet.' }
  return { code: 'KOK_NEDEN_ACIKLANMADI', title: 'Satış sapmasının kök nedeni açıklanmadı', severity: 'bad', evidence, personnelClaim: 'inconclusive', requiredAction: 'Fiş, sepet, stok, kategori ve yönetici kırılımıyla kanıt sun.' }
}
