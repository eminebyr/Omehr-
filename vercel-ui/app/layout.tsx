import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'OMEHR | İş Gücü Optimizasyon Platformu',
  description: 'Norm kadro, iş gücü, transfer ve yönetim analitiği platformu',
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  )
}
