import { createClient } from '@supabase/supabase-js'
import { NextRequest, NextResponse } from 'next/server'
import { PUBLIC_SUPABASE_KEY, PUBLIC_SUPABASE_URL } from '@/lib/supabase-config'

export const runtime = 'nodejs'
export const maxDuration = 60

export async function POST(request: NextRequest) {
  const bearer = request.headers.get('authorization')
  const accessToken = bearer?.startsWith('Bearer ') ? bearer.slice(7).trim() : ''

  if (!accessToken) {
    return NextResponse.json({ error: 'Oturum doğrulanamadı.' }, { status: 401 })
  }

  const authClient = createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  })
  const { data, error } = await authClient.auth.getUser(accessToken)
  if (error || !data.user) {
    return NextResponse.json({ error: 'Oturum geçersiz veya süresi dolmuş.' }, { status: 401 })
  }

  const scopedClient = createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: { Authorization: `Bearer ${accessToken}` } },
  })
  const { data: access, error: accessError } = await scopedClient
    .from('omehr_user_access')
    .select('role_code')
    .eq('auth_user_id', data.user.id)
    .eq('active', true)
    .maybeSingle()
  const role = String(access?.role_code ?? '').toLocaleUpperCase('tr-TR')
  if (accessError || !['ADMIN', 'HR_DIRECTOR', 'IK_DIREKTORU'].includes(role)) {
    return NextResponse.json({ error: 'Motoru çalıştırma yetkiniz bulunmuyor.' }, { status: 403 })
  }

  const engineUrl = process.env.OMEHR_ENGINE_API_URL?.trim()
  const engineSecret = process.env.OMEHR_ENGINE_API_SECRET?.trim()
  if (!engineUrl || !engineSecret) {
    return NextResponse.json(
      { error: 'Railway motor bağlantısı Vercel ortamında tanımlı değil.' },
      { status: 503 },
    )
  }

  try {
    const response = await fetch(engineUrl, {
      method: 'POST',
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        'X-Engine-Secret': engineSecret,
      },
      body: JSON.stringify({ requested_by: data.user.id }),
      cache: 'no-store',
      signal: AbortSignal.timeout(55_000),
    })
    const result = await response.json().catch(() => ({ error: 'Motor geçersiz yanıt döndürdü.' }))
    return NextResponse.json(result, { status: response.status })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Bilinmeyen bağlantı hatası'
    return NextResponse.json({ error: `Railway motoruna ulaşılamadı: ${message}` }, { status: 502 })
  }
}
