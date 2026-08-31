import { createClient } from '@supabase/supabase-js'
import { PUBLIC_SUPABASE_KEY, PUBLIC_SUPABASE_URL } from './supabase-config'

// Supabase Project URL ve publishable key tarayıcıda kullanılmak üzere tasarlanmıştır.
// Vercel environment variable varsa onu kullanır; Production kapsamı henüz
// tanımlı değilse güvenli public fallback sayesinde uygulama yine çalışır.
// Secret/service-role anahtarı hiçbir zaman frontend koduna konmaz.
const supabaseUrl = PUBLIC_SUPABASE_URL
const supabaseKey = PUBLIC_SUPABASE_KEY

export const supabaseConfigured = Boolean(supabaseUrl && supabaseKey)

export const supabase = createClient(supabaseUrl, supabaseKey, {
  auth: {
    persistSession: true,
    autoRefreshToken: true,
    detectSessionInUrl: true,
  },
})
