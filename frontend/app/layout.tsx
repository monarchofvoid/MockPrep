/**
 * VYAS v2.0 — Root Layout (Next.js App Router)
 * ==============================================
 * Root layout for all pages.
 *
 * Responsibilities:
 * 1. Load Google Fonts (replaces index.html <link> tags)
 * 2. Apply global CSS
 * 3. Wrap with AppProviders (auth initialization)
 * 4. Set default metadata (title, description, OG tags)
 *
 * Migration notes:
 * - Replaces index.html from Vite frontend
 * - Fonts loaded with next/font/google (optimized)
 * - No Razorpay script here (loaded lazily on-demand)
 */

import type { Metadata } from 'next'
import { Cinzel, DM_Sans, JetBrains_Mono } from 'next/font/google'
import { AppProviders } from '@/components/AppProviders'
import '../styles/globals.css'

// Font configurations
const cinzel = Cinzel({
  subsets: ['latin'],
  weight: ['600', '700', '800'],
  variable: '--font-display',
  display: 'swap',
})

const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700', '800'],
  variable: '--font-body',
  display: 'swap',
})

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['500', '700'],
  variable: '--font-mono',
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'VYAS — Virtual Yield Assessment System',
  description:
    'AI-powered exam preparation platform. Mock tests, performance analytics, and personalized AI tutoring for UPSC, GATE, CAT, JEE, and CUET.',
  keywords: [
    'exam preparation',
    'mock tests',
    'AI tutor',
    'UPSC',
    'GATE',
    'CAT',
    'JEE',
    'CUET',
    'online learning',
  ],
  authors: [{ name: 'VYAS Team' }],
  creator: 'VYAS',
  publisher: 'VYAS',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000'),
  openGraph: {
    title: 'VYAS — Virtual Yield Assessment System',
    description: 'AI-powered exam preparation platform with mock tests and personalized tutoring.',
    url: '/',
    siteName: 'VYAS',
    locale: 'en_US',
    type: 'website',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'VYAS — Virtual Yield Assessment System',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'VYAS — Virtual Yield Assessment System',
    description: 'AI-powered exam preparation platform with mock tests and personalized tutoring.',
    images: ['/og-image.png'],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
  },
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="en" className={`${cinzel.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}>
      <head>
        {/* Favicon */}
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  )
}