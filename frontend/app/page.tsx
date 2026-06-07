/**
 * VYAS v2.0 — Landing Page (Next.js)
 * ====================================
 * Entry point for unauthenticated users.
 *
 * Migration note:
 * - Entire page is a client component (maintains all animations & interactivity)
 * - Metadata defined in layout (not here, since it's a client component)
 */
import LandingClient from '@/components/Landing/Landingclient'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'VYAS - AI-Powered Exam Preparation Platform',
  description: 'Prepare for CUET, AKTU, and other competitive exams with AI-generated mock tests and personalized learning.',
  keywords: ['exam preparation', 'mock tests', 'AI tutoring', 'CUET', 'AKTU', 'competitive exams', 'personalized learning', 'CBSE', 'ICSE', 'state boards', 'NEET', 'JEE', 'UPSC', 'SSC', 'bank exams',
    'AI-generated questions', 'performance analytics', 'study planner', 'mobile-friendly', 'affordable education', 'VYAS']
}

export default function LandingPage() {
  return <LandingClient />
}