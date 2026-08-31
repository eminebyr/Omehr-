import { createClient } from '@supabase/supabase-js'

// Supabase Project URL ve publishable key tarayıcıda kullanılmak üzere tasarlanmıştır.
// Vercel environment variable varsa onu kullanır; Production kapsamı henüz
// tanımlı değilse güvenli public fallback sayesinde uygulama yine çalışır.
// Secret/service-role anahtarı hiçbir zaman frontend koduna konmaz.
const PUBLIC_SUPABASE_URL = 'https://teemjqigwuseznifylhk.supabase.co'
const PUBLIC_SUPABASE_KEY = 'sb_publishable_sc8rDr0zCI8xZBs-bJ6KyA_bcnnwDvk'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || PUBLIC_SUPABASE_URL
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || PUBLIC_SUPABASE_KEY

export const supabaseConfigured = Boolean(supabaseUrl && supabaseKey)

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})
