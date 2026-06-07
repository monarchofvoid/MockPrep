'use client'

/**
 * VYAS v2.0 — Landing Page Client Component (Production v2.1.5)
 * ───────────────────────────────────────────────────────────────
 * v2.1.5 API migration:
 *   - Removed `VYASApiError` import (class removed from api.ts)
 *     → replaced with `isApiError` type guard throughout
 *   - All existing auth functionality, animations, and visual content
 *     are 100% preserved.
 *
 * Note: the authStore actions (login, initiateSignup, verifyOTP, resendOTP)
 * are called via useAuthStore — those already use the hardened api.ts
 * internally through the updated authStore.ts. No direct api.ts calls here.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { useAuthStore } from '@/stores/authStore'
import { isApiError } from '@/lib/api'
import VyasLogo from '@/components/VyasLogo'
import VyasIntro from '@/components/VyasIntro'
import styles from '@/styles/Landing.module.css'

/* ─── SVG Icon Library ──────────────────────────────────────────────────────── */

const SvgStar = ({ filled = true }: { filled?: boolean }) => (
  <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.2">
    <polygon points="8,1.5 10.09,5.74 14.78,6.45 11.39,9.76 12.18,14.44 8,12.24 3.82,14.44 4.61,9.76 1.22,6.45 5.91,5.74" />
  </svg>
)

const SvgShieldCheck = () => (
  <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M8 1.5L2 4v4.5c0 3.3 2.5 6 6 7 3.5-1 6-3.7 6-7V4z" />
    <polyline points="5.5,8 7,9.5 10.5,6" />
  </svg>
)

const SvgCheckCircle = () => (
  <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="8" cy="8" r="6.5" />
    <polyline points="5,8 7,10 11,6" />
  </svg>
)

const SvgDiamond = () => (
  <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="8,2 14,8 8,14 2,8" />
  </svg>
)

const SvgSpark = () => (
  <svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true" fill="currentColor">
    <path d="M8 1l1.5 5H15l-4.5 3.3L12 15 8 11.7 4 15l1.5-5.7L1 6h5.5z" />
  </svg>
)

const SvgXClose = () => (
  <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <line x1="4" y1="4" x2="16" y2="16" />
    <line x1="16" y1="4" x2="4" y2="16" />
  </svg>
)

const Icon = {
  Clock: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="100%" height="100%" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  BarChart: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="100%" height="100%" aria-hidden="true">
      <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
    </svg>
  ),
  SearchPlus: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="100%" height="100%" aria-hidden="true">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
      <line x1="11" y1="8" x2="11" y2="14" /><line x1="8" y1="11" x2="14" y2="11" />
    </svg>
  ),
  TrendUp: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="100%" height="100%" aria-hidden="true">
      <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
    </svg>
  ),
  LoopOff: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <polyline points="17 1 21 5 17 9" /><path d="M3 11V9a4 4 0 014-4h14" />
      <polyline points="7 23 3 19 7 15" /><path d="M21 13v2a4 4 0 01-4 4H3" />
    </svg>
  ),
  Hash: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <line x1="4" y1="9" x2="20" y2="9" /><line x1="4" y1="15" x2="20" y2="15" />
      <line x1="10" y1="3" x2="8" y2="21" /><line x1="16" y1="3" x2="14" y2="21" />
    </svg>
  ),
  XCircle: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  ),
  Timer: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
      <line x1="12" y1="2" x2="12" y2="4" />
    </svg>
  ),
  Cpu: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" />
      <path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" />
    </svg>
  ),
  BookOpen: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <path d="M2 3h6a4 4 0 014 4v14a3 3 0 00-3-3H2z" /><path d="M22 3h-6a4 4 0 00-4 4v14a3 3 0 013-3h7z" />
    </svg>
  ),
  Target: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
    </svg>
  ),
  Activity: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="18" height="18" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  FileEdit: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  ),
  Zap: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  Search: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  PieChart: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <path d="M21.21 15.89A10 10 0 118 2.83" /><path d="M22 12A10 10 0 0012 2v10z" />
    </svg>
  ),
  Crosshair: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <circle cx="12" cy="12" r="10" /><line x1="22" y1="12" x2="18" y2="12" />
      <line x1="6" y1="12" x2="2" y2="12" /><line x1="12" y1="6" x2="12" y2="2" /><line x1="12" y1="22" x2="12" y2="18" />
    </svg>
  ),
  RefreshCw: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
    </svg>
  ),
  Flame: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <path d="M8.5 14.5A2.5 2.5 0 0011 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 11-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 002.5 3z" />
    </svg>
  ),
  Microscope: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <path d="M6 18h8" /><path d="M3 22h18" /><path d="M14 22a7 7 0 10-4-12.874V4a2 2 0 10-4 0v6.126A7 7 0 0014 22z" />
    </svg>
  ),
  MessageSquare: () => (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
      <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
    </svg>
  ),
  ArrowRight: () => (
    <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="3" y1="8" x2="13" y2="8" /><polyline points="9,4 13,8 9,12" />
    </svg>
  ),
}

/* ─── Data ──────────────────────────────────────────────────────────────────── */

const FEATURES = [
  { kicker: 'Simulate', title: 'Real exam conditions',     desc: 'Timed papers, structured navigation, review states, and submission discipline built into every attempt.',          icon: <Icon.Clock /> },
  { kicker: 'Diagnose', title: 'Performance intelligence', desc: 'Score, accuracy, pace, and topic mastery are tracked across attempts so progress becomes visible.',               icon: <Icon.BarChart /> },
  { kicker: 'Review',   title: 'Clear solution analysis',  desc: 'Every result opens into question-level review with correct answers, explanations, and behaviour signals.',        icon: <Icon.SearchPlus /> },
  { kicker: 'Ascend',   title: 'Focused improvement',      desc: 'Weak areas surface naturally, helping learners spend their next session where it matters most.',                 icon: <Icon.TrendUp /> },
]

const EXAMS = ['CUET', 'GATE', 'CAT', 'JEE', 'UPSC']

const TRUST_ITEMS = [
  'AI-Powered Analysis',
  'Real Exam Experience',
  'Performance Intelligence',
  'Privacy First',
  'Actively Developed',
]

const PROBLEMS = [
  { icon: <Icon.LoopOff />, title: 'Endless practice without direction', desc: 'Hours spent on questions with no clarity on what to improve.' },
  { icon: <Icon.Hash />,    title: 'Scores without explanations',        desc: 'You see 68% but have no idea why or what to fix next.' },
  { icon: <Icon.XCircle />, title: 'No improvement tracking',            desc: 'Every attempt feels isolated from the last.' },
  { icon: <Icon.Timer />,   title: 'Weak time management',               desc: 'Running out of time without knowing where it went.' },
]

const SOLUTIONS = [
  { icon: <Icon.Cpu />,        title: 'AI-powered insights',      desc: 'Every attempt produces a full performance intelligence report.' },
  { icon: <Icon.BookOpen />,   title: 'Detailed explanations',    desc: 'Understand why each answer is right or wrong, instantly.' },
  { icon: <Icon.Target />,     title: 'Topic mastery tracking',   desc: 'Weak areas surface automatically across all attempts.' },
  { icon: <Icon.Activity />,   title: 'Performance analytics',    desc: 'Time distribution, accuracy trends, and behavioural patterns.' },
]

const JOURNEY_STEPS = [
  { icon: <Icon.FileEdit />,   title: 'Take a Mock',       desc: 'Real exam conditions' },
  { icon: <Icon.Zap />,        title: 'Get Evaluated',     desc: 'Instant AI analysis' },
  { icon: <Icon.Search />,     title: 'Analyse Mistakes',  desc: 'Question-level review' },
  { icon: <Icon.PieChart />,   title: 'Track Progress',    desc: 'Cross-attempt trends' },
  { icon: <Icon.Crosshair />,  title: 'Improve Weak Areas',desc: 'Targeted practice' },
  { icon: <Icon.RefreshCw />,  title: 'Repeat & Grow',     desc: 'Measurable ascent' },
]

const PILLARS = [
  { icon: <Icon.Flame />,        title: 'Consistency', desc: 'Build sustainable learning habits that compound over time. Regular practice in structured conditions beats cramming every time.' },
  { icon: <Icon.Microscope />,   title: 'Clarity',     desc: "Understand exactly what needs improvement. VYAS surfaces your blind spots so you never waste time on things you already know." },
  { icon: <Icon.MessageSquare />,title: 'Feedback',    desc: 'Receive actionable performance intelligence after every attempt. Not a score — a diagnosis. Not motivation — direction.' },
]

const REVIEWS_SET_1 = [
  { name: 'Aman Sharma',  role: 'GATE Aspirant',             initial: 'A', text: "VYAS helped me identify patterns in my mistakes that I never noticed before. The analytics are genuinely useful — not just a score, but a full breakdown." },
  { name: 'Priya Verma',  role: 'B.Tech Student',            initial: 'P', text: "The AI-generated mocks feel surprisingly close to actual exam difficulty. It's a great practice resource for competitive exams." },
  { name: 'Rohit Singh',  role: 'Software Engineer',         initial: 'R', text: "I use VYAS for technical assessment preparation. The detailed performance breakdown is excellent and saves a lot of guesswork." },
  { name: 'Neha Gupta',   role: 'MBA Entrance Aspirant',     initial: 'N', text: "The strongest feature is the post-test analysis. It tells you exactly where improvement is needed — which topics, which question types." },
  { name: 'Arjun Mehta',  role: 'Competitive Exam Candidate',initial: 'A', text: "Instead of just giving scores, VYAS explains performance. That's what makes it genuinely different from other platforms." },
]

const REVIEWS_SET_2 = [
  { name: 'Karan Malhotra',role: 'Final Year Student',      initial: 'K', text: "The UI feels professional and the mock generation process is extremely smooth. Highly recommended for serious aspirants." },
  { name: 'Sneha Kapoor',  role: 'Government Exam Aspirant',initial: 'S', text: "The time management insights helped me more than any practice book. I finally understand where my time actually goes." },
  { name: 'Vivek Jain',    role: 'Engineering Graduate',    initial: 'V', text: "Topic-wise performance tracking helped me focus only on weak areas instead of wasting time on what I already know." },
  { name: 'Ishita Arora',  role: 'University Student',      initial: 'I', text: "Clean interface, useful explanations, and very detailed feedback after each test. Exactly what exam prep should look like." },
  { name: 'Harsh Rajput',  role: 'Placement Preparation',   initial: 'H', text: "The analytics dashboard makes preparation feel measurable instead of random. I can actually see myself improving." },
]

const ROADMAP_DONE = [
  'Mock Tests across multiple exams',
  'Performance Analytics Dashboard',
  'AI Mock Generator',
  'Topic Mastery Tracking',
  'Question-level Review',
  'Wallet & Credit System',
]

const ROADMAP_UPCOMING = [
  'Study Planner',
  'AI Mentor',
  'Personalized Learning Paths',
  'Smart Revision System',
]

/* ─── Hooks ─────────────────────────────────────────────────────────────────── */

function useScrollReveal(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { setVisible(true); obs.disconnect() } },
      { threshold }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return [ref, visible] as const
}

function useCountUp(target: number, duration = 1400, active = false) {
  const [count, setCount] = useState(0)
  useEffect(() => {
    if (!active) return
    let start: number | null = null
    let raf: number
    const step = (ts: number) => {
      if (!start) start = ts
      const pct = Math.min((ts - start) / duration, 1)
      const eased = 1 - Math.pow(1 - pct, 3)
      setCount(Math.round(eased * target))
      if (pct < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, duration, active])
  return count
}

function useScrollProgress() {
  const [progress, setProgress] = useState(0)
  useEffect(() => {
    const onScroll = () => {
      const el = document.documentElement
      const scrolled = el.scrollTop
      const total = el.scrollHeight - el.clientHeight
      setProgress(total > 0 ? (scrolled / total) * 100 : 0)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])
  return progress
}

/* ─── Sub-components ────────────────────────────────────────────────────────── */

function ReviewStars() {
  return (
    <span className={styles.reviewStars} aria-label="5 stars">
      {[0,1,2,3,4].map(i => <SvgStar key={i} />)}
    </span>
  )
}

function VerifiedBadge() {
  return (
    <span className={styles.reviewVerified}>
      <SvgShieldCheck />
      Verified
    </span>
  )
}

function StatCounter({ value, suffix, label }: { value: number; suffix: string; label: string }) {
  const [ref, visible] = useScrollReveal(0.3)
  const count = useCountUp(value, 1200, visible)
  return (
    <div ref={ref} className={`${styles.statItem} ${visible ? styles.statVisible : ''}`}>
      <span className={styles.statValue}>{count}{suffix}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  )
}

function FeatureCard({ feature, index }: { feature: typeof FEATURES[0]; index: number }) {
  const [ref, visible] = useScrollReveal(0.1)
  return (
    <article
      ref={ref}
      className={`${styles.featureCard} ${visible ? styles.cardVisible : ''}`}
      style={{ '--card-delay': `${index * 80}ms` } as React.CSSProperties}
    >
      <div className={styles.featureIconWrap}>{feature.icon}</div>
      <span className={styles.featureKicker}>{feature.kicker}</span>
      <h3 className={styles.featureTitle}>{feature.title}</h3>
      <p className={styles.featureDesc}>{feature.desc}</p>
    </article>
  )
}

function PsCard({ item, isSolution, index }: { item: { icon: React.ReactNode; title: string; desc: string }; isSolution: boolean; index: number }) {
  const [ref, visible] = useScrollReveal(0.1)
  return (
    <div
      ref={ref}
      className={`${styles.psCard} ${isSolution ? styles.psCardSolution : ''} ${visible ? styles.psCardVisible : ''}`}
      style={{ '--ps-delay': `${index * 100}ms` } as React.CSSProperties}
    >
      <div className={`${styles.psIcon} ${isSolution ? styles.psIconSolution : styles.psIconProblem}`}>
        {item.icon}
      </div>
      <div className={styles.psCardText}>
        <p className={styles.psCardTitle}>{item.title}</p>
        <p className={styles.psCardDesc}>{item.desc}</p>
      </div>
    </div>
  )
}

function ReviewCard({ review }: { review: typeof REVIEWS_SET_1[0] }) {
  return (
    <div className={styles.reviewCard}>
      <div className={styles.reviewCardHeader}>
        <div className={styles.reviewAvatar}>{review.initial}</div>
        <div className={styles.reviewMeta}>
          <span className={styles.reviewName}>{review.name}</span>
          <span className={styles.reviewRole}>{review.role}</span>
        </div>
        <VerifiedBadge />
      </div>
      <ReviewStars />
      <p className={styles.reviewText}>{review.text}</p>
    </div>
  )
}

function ReviewStatCounter({ value, suffix, label, delay }: { value: number; suffix: string; label: string; delay: number }) {
  const [ref, visible] = useScrollReveal(0.2)
  const count = useCountUp(value, 1200, visible)
  return (
    <div
      ref={ref}
      className={`${styles.reviewStatItem} ${visible ? styles.reviewStatItemVisible : ''}`}
      style={{ '--rstat-delay': `${delay}ms` } as React.CSSProperties}
    >
      <span className={styles.reviewStatValue}>{count}{suffix}</span>
      <span className={styles.reviewStatLabel}>{label}</span>
    </div>
  )
}

/* ─── Eye icons ─────────────────────────────────────────────────────────────── */

const SvgEye = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
)

const SvgEyeOff = () => (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
    strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
)

const SvgGoogle = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
)

/* ─── Password strength ─────────────────────────────────────────────────────── */

interface StrengthResult {
  level: 'empty' | 'weak' | 'fair' | 'good' | 'strong'
  score: number
  failures: string[]
  isValid: boolean
}

function analysePassword(pw: string): StrengthResult {
  if (!pw) return { level: 'empty', score: 0, failures: [], isValid: false }
  const rules = [
    { label: 'At least 9 characters',                   met: pw.length >= 9 },
    { label: 'At least one uppercase letter (A–Z)',      met: /[A-Z]/.test(pw) },
    { label: 'At least one digit (1–9)',                 met: /[1-9]/.test(pw) },
    { label: 'At least one special character (@#&!%…)',  met: /[^A-Za-z0-9]/.test(pw) },
  ]
  const score    = rules.filter((r) => r.met).length
  const failures = rules.filter((r) => !r.met).map((r) => r.label)
  const isValid  = score === 4
  const level: StrengthResult['level'] =
    score === 4 ? 'strong' : score === 3 ? 'good' : score === 2 ? 'fair' : 'weak'
  return { level, score, failures, isValid }
}

function StrengthMeter({ password }: { password: string }) {
  if (!password) return null
  const { level, score, failures } = analysePassword(password)
  const activeColour =
    level === 'strong' ? '#22c55e' : level === 'good' ? '#d4a843' :
    level === 'fair'   ? '#f59e0b' : '#ef4444'
  const labelColour =
    level === 'strong' ? '#86efac' : level === 'good' ? '#f0c060' :
    level === 'fair'   ? '#fbbf24' : '#fca5a5'
  return (
    <div style={{ marginTop: '4px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '5px', marginBottom: failures.length ? '6px' : '0' }}>
        {[0, 1, 2, 3].map((i) => (
          <div key={i} style={{
            flex: 1, height: '4px', borderRadius: '999px',
            background: i < score ? activeColour : '#2a2a2a',
            transition: 'background 250ms ease',
          }} />
        ))}
        <span style={{
          minWidth: '48px', marginLeft: '6px', color: labelColour,
          fontSize: '11px', fontWeight: 800, textTransform: 'uppercase' as const,
          letterSpacing: '0.06em',
        }}>{level}</span>
      </div>
      {failures.length > 0 && (
        <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column' as const, gap: '3px' }}>
          {failures.map((f) => (
            <li key={f} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--text-muted)', lineHeight: 1.4 }}>
              <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#ef4444', flexShrink: 0, display: 'inline-block' }} />
              {f}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

/* ─── Main Component ────────────────────────────────────────────────────────── */

export default function LandingClient() {
  const { user, login, initiateSignup, verifyOTP, resendOTP, isAuthenticated } = useAuthStore()
  const router       = useRouter()
  const searchParams = useSearchParams()
  const from         = searchParams.get('from') || '/dashboard'
  const scrollProgress = useScrollProgress()

  const [modalOpen,    setModalOpen]    = useState(false)
  const [tab,          setTab]          = useState<'login' | 'signup'>('login')
  const [modalScreen,  setModalScreen]  = useState<'form' | 'otp'>('form')
  const [formData,     setFormData]     = useState({ name: '', email: '', password: '' })
  const [otpValue,     setOtpValue]     = useState('')
  const [error,        setError]        = useState('')
  const [loading,      setLoading]      = useState(false)
  const [activeExam,   setActiveExam]   = useState(0)
  const [showPassword, setShowPassword] = useState(false)
  const [otpSecondsLeft,  setOtpSecondsLeft]  = useState(0)
  const [resendDisabled,  setResendDisabled]  = useState(false)

  // BUG FIX v2.2.0: Handle OAuth error redirects from the backend.
  // Backend sends /?error=oauth_denied | email_not_verified | account_error
  // Callback page sends /?error=oauth_failed
  // Previously these landed here silently — modal never opened, no error shown.
  useEffect(() => {
    const oauthError = searchParams.get('error')
    if (!oauthError) return
    const messages: Record<string, string> = {
      oauth_denied:         'Google sign-in was cancelled. Please try again.',
      email_not_verified:   'Your Google account email is not verified. Please verify it with Google first.',
      account_error:        'There was a problem with your account. Please contact support if this persists.',
      oauth_failed:         'Sign-in failed. Please try again or use email and password.',
    }
    const msg = messages[oauthError] || 'Sign-in failed. Please try again.'
    setTab('login')
    setError(msg)
    setModalScreen('form')
    setModalOpen(true)
    // Remove the ?error= param from the URL so a page refresh doesn't re-show the error
    router.replace('/', { scroll: false })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []) // intentionally run once on mount only

  useEffect(() => {
    const id = setInterval(() => setActiveExam((p) => (p + 1) % EXAMS.length), 1800)
    return () => clearInterval(id)
  }, [])

  useEffect(() => {
    if (isAuthenticated && user) router.replace(from)
  }, [isAuthenticated, user, router, from])

  useEffect(() => {
    if (otpSecondsLeft <= 0) return
    const id = setInterval(() => setOtpSecondsLeft((s) => Math.max(0, s - 1)), 1000)
    return () => clearInterval(id)
  }, [otpSecondsLeft])

  const [heroRef,         heroVisible]         = useScrollReveal(0.05)
  const [aiRef,           aiVisible]           = useScrollReveal(0.1)
  const [ctaRef,          ctaVisible]          = useScrollReveal(0.1)
  const [journeyRef,      journeyVisible]      = useScrollReveal(0.1)
  const [roadmapContentRef, roadmapContentVisible] = useScrollReveal(0.1)
  const [roadmapVisualRef,  roadmapVisualVisible]   = useScrollReveal(0.1)

  const openModal = useCallback((defaultTab: 'login' | 'signup' = 'login') => {
    setTab(defaultTab)
    setError('')
    setFormData({ name: '', email: '', password: '' })
    setOtpValue('')
    setShowPassword(false)
    setModalScreen('form')
    setModalOpen(true)
  }, [])

  const closeModal = useCallback(() => {
    if (loading) return
    setModalOpen(false)
    setError('')
    setModalScreen('form')
    setOtpValue('')
    setShowPassword(false)
  }, [loading])

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
    setFormData((prev) => ({ ...prev, [e.target.name]: e.target.value }))

  const pwStrength = analysePassword(formData.password)

  const handleGoogleAuth = () => {
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '')
    window.location.href = `${apiBase}/auth/oauth/google`
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (tab === 'login') {
      setLoading(true)
      try {
        await login(formData.email, formData.password)
        router.push(from)
      } catch (err: unknown) {
        // FIX: was `err instanceof VYASApiError` → `isApiError(err)`
        if (isApiError(err)) setError(err.message || 'Something went wrong.')
        else setError('Something went wrong. Please try again.')
      } finally { setLoading(false) }
      return
    }
    // Signup
    if (!formData.name.trim()) { setError('Please enter your full name.'); return }
    if (!pwStrength.isValid) { setError('Please meet all password requirements shown below.'); return }
    setLoading(true)
    try {
      const expiresIn = await initiateSignup(formData.name.trim(), formData.email, formData.password)
      setOtpSecondsLeft(expiresIn)
      setResendDisabled(false)
      setOtpValue('')
      setModalScreen('otp')
    } catch (err: unknown) {
      // FIX: was `err instanceof VYASApiError` → `isApiError(err)`
      if (isApiError(err)) {
        const msg = err.message || ''
        if (
          msg.toLowerCase().includes('already registered') ||
          msg.toLowerCase().includes('already taken')
        ) {
          setTab('login')
          setFormData((prev) => ({ ...prev, password: '' }))
          setShowPassword(false)
          setError('This email is already registered. Enter your password below to sign in.')
        } else {
          setError(msg || 'Something went wrong. Please try again.')
        }
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally { setLoading(false) }
  }

  const handleOTPSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (otpValue.length !== 6) { setError('Please enter the 6-digit code.'); return }
    setLoading(true)
    try {
      await verifyOTP(formData.email, otpValue)
      router.push(from)
    } catch (err: unknown) {
      // FIX: was `err instanceof VYASApiError` → `isApiError(err)`
      if (isApiError(err)) {
        const msg = err.message || ''
        if (msg.toLowerCase().includes('already registered') || msg.toLowerCase().includes('already taken')) {
          setError('This email is already registered. Please sign in instead.')
          setTimeout(() => { setModalScreen('form'); setTab('login'); setOtpValue(''); setError('') }, 2200)
        } else {
          setError(msg || 'Incorrect code. Please try again.')
        }
      } else {
        setError('Incorrect code. Please try again.')
      }
    } finally { setLoading(false) }
  }

  const handleResendOTP = async () => {
    setError('')
    setResendDisabled(true)
    try {
      await resendOTP(formData.email)
      setOtpSecondsLeft(600)
      setOtpValue('')
    } catch (err: unknown) {
      // FIX: was `err instanceof VYASApiError` → `isApiError(err)`
      if (isApiError(err)) setError(err.message || 'Failed to resend code.')
      else setError('Failed to resend code.')
      setResendDisabled(false)
    }
  }

  const handleChangeEmail = () => {
    setModalScreen('form')
    setTab('signup')
    setOtpValue('')
    setError('')
    setFormData((prev) => ({ ...prev, password: '' }))
    setShowPassword(false)
  }

  const formatCountdown = (s: number) =>
    `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`

  const railLeftReviews  = [...REVIEWS_SET_1, ...REVIEWS_SET_1]
  const railRightReviews = [...REVIEWS_SET_2, ...REVIEWS_SET_2]

  return (
    <>
      <VyasIntro />

      <div className={styles.page}>
        <div className={styles.scrollProgress} style={{ width: `${scrollProgress}%` }} aria-hidden="true" />

        {/* HEADER */}
        <header className={styles.header}>
          <div className={styles.headerInner}>
            <div className={styles.brand}>
              <VyasLogo variant="gold" size={36} />
              <span className={styles.brandName}>VYAS</span>
            </div>
            <div className={styles.headerActions}>
              <button className={styles.loginLink} onClick={() => openModal('login')}>Sign in</button>
              <button className={styles.signupBtn} onClick={() => openModal('signup')}>Get started</button>
            </div>
          </div>
        </header>

        <main>
          {/* HERO */}
          <section className={styles.hero}>
            <div className={styles.heroBgGrid} aria-hidden="true" />
            <div className={styles.heroBgOrb1} aria-hidden="true" />
            <div className={styles.heroBgOrb2} aria-hidden="true" />

            <div ref={heroRef} className={`${styles.heroInner} ${heroVisible ? styles.heroVisible : ''}`}>
              <VyasLogo variant="gold" size={108} animate className={styles.heroLogo} />

              <div className={styles.trustRow}>
                {TRUST_ITEMS.map((t) => (
                  <span key={t} className={styles.trustChip}>
                    <span className={styles.trustDot} aria-hidden="true" />
                    {t}
                  </span>
                ))}
              </div>

              <h1 className={styles.heroTitle}>
                Practice Smarter.
                <br />
                <span className={styles.heroTitleAccent}>Perform Better.</span>
              </h1>

              <p className={styles.heroSub}>
                VYAS transforms every mock test into a complete performance intelligence report — revealing
                strengths, weaknesses, behavioural patterns, and personalised improvement opportunities.
              </p>

              <div className={styles.examPills}>
                {EXAMS.map((exam, i) => (
                  <span key={exam} className={`${styles.examPill} ${i === activeExam ? styles.examPillActive : ''}`}>
                    {exam}
                  </span>
                ))}
              </div>

              <div className={styles.heroCtas}>
                <button className={styles.primaryCta} onClick={() => openModal('signup')}>
                  Start practising free
                  <span className={styles.ctaArrow}><Icon.ArrowRight /></span>
                </button>
                <button className={styles.secondaryCta} onClick={() => openModal('login')}>Continue ascent</button>
              </div>

              <div className={styles.scrollHint} aria-hidden="true">
                <span className={styles.scrollLine} />
                <span className={styles.scrollText}>scroll to explore</span>
              </div>
            </div>
          </section>

          {/* STATS */}
          <section className={styles.statsSection} aria-label="Platform statistics">
            <div className={styles.statsInner}>
              {[
                { value: 1000, suffix: '+', label: 'Mocks Generated' },
                { value: 5000, suffix: '+', label: 'Questions Attempted' },
                { value: 50,   suffix: '+', label: 'Subjects Covered' },
                { value: 95,   suffix: '%', label: 'User Satisfaction' },
              ].map((s) => (
                <StatCounter key={s.label} value={s.value} suffix={s.suffix} label={s.label} />
              ))}
            </div>
          </section>

          <div className={styles.sectionSep} aria-hidden="true" />

          {/* WHY VYAS EXISTS */}
          <section className={styles.whySection}>
            <div className={styles.whyInner}>
              <div className={styles.whyHeaderCenter}>
                <span className={styles.sectionKicker}>The problem we solve</span>
                <h2 className={styles.sectionTitle}>Most Students Don&apos;t Need More Questions</h2>
                <p className={styles.sectionSub}>
                  They need to understand why they got the ones they had wrong — and where to focus next.
                </p>
              </div>
              <div className={styles.problemSolutionGrid}>
                <div className={styles.problemCol}>
                  <span className={`${styles.colLabel} ${styles.colLabelProblem}`}>Without VYAS</span>
                  {PROBLEMS.map((p, i) => <PsCard key={p.title} item={p} isSolution={false} index={i} />)}
                </div>
                <div className={styles.solutionCol}>
                  <span className={`${styles.colLabel} ${styles.colLabelSolution}`}>With VYAS</span>
                  {SOLUTIONS.map((s, i) => <PsCard key={s.title} item={s} isSolution={true} index={i} />)}
                </div>
              </div>
            </div>
          </section>

          <div className={styles.sectionSep} aria-hidden="true" />

          {/* STUDENT JOURNEY */}
          <section className={styles.journeySection}>
            <div className={styles.journeyInner}>
              <div className={styles.sectionHeader}>
                <span className={styles.sectionKicker}>The journey</span>
                <h2 className={styles.sectionTitle}>Six Steps to Measurable Improvement</h2>
                <p className={styles.sectionSub}>
                  Every cycle makes you sharper. The system is designed so each attempt builds on the last.
                </p>
              </div>
              <div ref={journeyRef} className={styles.journeyTimeline} aria-label="Student improvement journey">
                {JOURNEY_STEPS.map((step, i) => (
                  <div
                    key={step.title}
                    className={`${styles.journeyStep} ${journeyVisible ? styles.journeyStepVisible : ''}`}
                    style={{ '--journey-delay': `${i * 100}ms` } as React.CSSProperties}
                  >
                    <div className={styles.journeyDot}>
                      <span className={styles.journeyDotIcon}>{step.icon}</span>
                      <span className={styles.journeyNum}>{i + 1}</span>
                    </div>
                    <p className={styles.journeyStepTitle}>{step.title}</p>
                    <p className={styles.journeyStepDesc}>{step.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <div className={styles.sectionSep} aria-hidden="true" />

          {/* HOW IT WORKS */}
          <section className={styles.howSection}>
            <div className={styles.howInner}>
              <div className={styles.sectionHeader}>
                <span className={styles.sectionKicker}>Intelligence layer</span>
                <h2 className={styles.sectionTitle}>Everything you need to ascend</h2>
                <p className={styles.sectionSub}>
                  From simulation to deep diagnosis — VYAS guides every step with precision and purpose.
                </p>
              </div>
              <div className={styles.stepsRow}>
                {[
                  { step: '01', title: 'Choose your exam',      desc: 'Browse mock papers across UPSC, GATE, CAT, JEE and CUET. Pick your challenge.' },
                  { step: '02', title: 'Train under pressure',   desc: 'Attempt tests in real exam conditions — timed, structured, and discipline-enforced from question one.' },
                  { step: '03', title: 'Ascend with insight',    desc: 'Review every answer, study your patterns. VYAS surfaces exactly where to focus next.' },
                ].map((step, i) => (
                  <div
                    key={step.step}
                    className={`${styles.step} ${styles.stepVisible}`}
                    style={{ '--step-delay': `${i * 120}ms` } as React.CSSProperties}
                  >
                    <div className={styles.stepNumber}>{step.step}</div>
                    <div className={styles.stepContent}>
                      <h3 className={styles.stepTitle}>{step.title}</h3>
                      <p className={styles.stepDesc}>{step.desc}</p>
                    </div>
                    {i < 2 && <div className={styles.stepConnector} aria-hidden="true" />}
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* FEATURES */}
          <section className={styles.features}>
            <div className={styles.featuresInner}>
              <div className={styles.sectionHeader}>
                <span className={styles.sectionKicker}>Practice system</span>
                <h2 className={styles.sectionTitle}>Built for deliberate preparation</h2>
                <p className={styles.sectionSub}>
                  Every feature is designed around one goal: measurable improvement per hour of practice.
                </p>
              </div>
              <div className={styles.featureGrid}>
                {FEATURES.map((feature, i) => <FeatureCard key={feature.title} feature={feature} index={i} />)}
              </div>
            </div>
          </section>

          {/* AI SPOTLIGHT */}
          <section className={styles.aiSection}>
            <div ref={aiRef} className={`${styles.aiInner} ${aiVisible ? styles.aiVisible : ''}`}>
              <div className={styles.aiContent}>
                <span className={styles.sectionKicker}>New · AI Generator</span>
                <h2 className={styles.aiTitle}>Never run out of<br />practice material</h2>
                <p className={styles.aiDesc}>
                  VYAS&apos;s AI Mock Generator creates fresh, exam-relevant questions on demand — calibrated to
                  your proficiency level and targeted at your weakest topics. Infinite practice. Zero repetition.
                </p>
                <ul className={styles.aiFeatureList}>
                  {[
                    'Topic-targeted generation',
                    'Difficulty calibrated to your level',
                    'Instant explanations & solutions',
                    'Synced with your performance data',
                  ].map((item) => (
                    <li key={item} className={styles.aiFeatureItem}>
                      <span className={styles.aiCheck} aria-hidden="true"><SvgSpark /></span>
                      {item}
                    </li>
                  ))}
                </ul>
                <button className={styles.primaryCta} onClick={() => openModal('signup')}>
                  Try AI generator free
                  <span className={styles.ctaArrow}><Icon.ArrowRight /></span>
                </button>
              </div>
              <div className={styles.aiVisual} aria-hidden="true">
                <div className={styles.aiCard}>
                  <div className={styles.aiCardHeader}>
                    <span className={styles.aiCardDot} /><span className={styles.aiCardDot} /><span className={styles.aiCardDot} />
                    <span className={styles.aiCardTitle}>AI Mock · Generating</span>
                  </div>
                  <div className={styles.aiCardBody}>
                    <div className={styles.aiLine} style={{ '--w': '90%' } as React.CSSProperties} />
                    <div className={styles.aiLine} style={{ '--w': '75%' } as React.CSSProperties} />
                    <div className={styles.aiLine} style={{ '--w': '60%' } as React.CSSProperties} />
                    <div className={styles.aiOptionRow}><div className={styles.aiOption}>A</div><div className={styles.aiOptionBar} style={{ '--w': '82%' } as React.CSSProperties} /></div>
                    <div className={styles.aiOptionRow}><div className={`${styles.aiOption} ${styles.aiOptionCorrect}`}>B</div><div className={`${styles.aiOptionBar} ${styles.aiOptionBarCorrect}`} style={{ '--w': '95%' } as React.CSSProperties} /></div>
                    <div className={styles.aiOptionRow}><div className={styles.aiOption}>C</div><div className={styles.aiOptionBar} style={{ '--w': '55%' } as React.CSSProperties} /></div>
                    <div className={styles.aiOptionRow}><div className={styles.aiOption}>D</div><div className={styles.aiOptionBar} style={{ '--w': '40%' } as React.CSSProperties} /></div>
                  </div>
                  <div className={styles.aiCardFooter}>
                    <span className={styles.aiTag}>UPSC GS-I</span>
                    <span className={styles.aiTag}>History</span>
                    <span className={styles.aiTag}>Medium</span>
                  </div>
                </div>
                <div className={styles.aiGlow} />
              </div>
            </div>
          </section>

          <div className={styles.sectionSep} aria-hidden="true" />

          {/* THREE PILLARS */}
          <section className={styles.pillarsSection}>
            <div className={styles.pillarsInner}>
              <div className={styles.sectionHeader} style={{ margin: '0 auto var(--space-7)', maxWidth: '640px', textAlign: 'center' }}>
                <span className={styles.sectionKicker}>Why students improve faster</span>
                <h2 className={styles.sectionTitle}>Three Principles, One Direction</h2>
              </div>
              <div className={styles.pillarsGrid}>
                {PILLARS.map((pillar, i) => (
                  <div
                    key={pillar.title}
                    className={`${styles.pillarCard} ${styles.pillarCardVisible}`}
                    style={{ '--pillar-delay': `${i * 100}ms` } as React.CSSProperties}
                  >
                    <div className={styles.pillarIcon}>{pillar.icon}</div>
                    <h3 className={styles.pillarTitle}>{pillar.title}</h3>
                    <p className={styles.pillarDesc}>{pillar.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <div className={styles.sectionSep} aria-hidden="true" />

          {/* REVIEWS */}
          <section className={styles.reviewsSection} aria-label="Student reviews">
            <div className={styles.reviewsInner}>
              <div className={styles.reviewsHeaderCenter}>
                <span className={styles.sectionKicker}>Social proof</span>
                <h2 className={styles.sectionTitle}>Trusted By Learners Who Want Results</h2>
                <p className={styles.sectionSub}>
                  Students, graduates, professionals, and competitive exam aspirants use VYAS to identify
                  weaknesses, track progress, and practice with purpose.
                </p>
              </div>
              <div className={styles.reviewRailsWrapper} aria-hidden="true">
                <div className={`${styles.reviewRail} ${styles.reviewRailLeft}`}>
                  {railLeftReviews.map((r, i) => <ReviewCard key={`l-${i}`} review={r} />)}
                </div>
                <div className={`${styles.reviewRail} ${styles.reviewRailRight}`}>
                  {railRightReviews.map((r, i) => <ReviewCard key={`r-${i}`} review={r} />)}
                </div>
              </div>
              <div className={styles.reviewStats}>
                {[
                  { value: 1000, suffix: '+', label: 'Mocks Generated',     delay: 0 },
                  { value: 5000, suffix: '+', label: 'Questions Attempted',  delay: 100 },
                  { value: 50,   suffix: '+', label: 'Subjects Covered',     delay: 200 },
                  { value: 95,   suffix: '%', label: 'User Satisfaction',    delay: 300 },
                ].map((s) => (
                  <ReviewStatCounter key={s.label} value={s.value} suffix={s.suffix} label={s.label} delay={s.delay} />
                ))}
              </div>
            </div>
          </section>

          <div className={styles.sectionSep} aria-hidden="true" />

          {/* ROADMAP + PHILOSOPHY */}
          <section className={styles.roadmapSection}>
            <div className={styles.roadmapInner}>
              <div
                ref={roadmapContentRef}
                className={`${styles.roadmapContent} ${roadmapContentVisible ? styles.roadmapContentVisible : ''}`}
              >
                <span className={styles.sectionKicker}>Future vision</span>
                <h2 className={styles.sectionTitle}>Where VYAS is headed</h2>
                <p className={styles.sectionSub}>
                  We&apos;re actively building the most intelligent exam preparation ecosystem.
                  Here&apos;s what&apos;s shipped and what&apos;s coming.
                </p>
                <div className={styles.roadmapGroup} style={{ marginTop: 'var(--space-6)' }}>
                  <span className={`${styles.roadmapGroupLabel} ${styles.roadmapGroupLabelDone}`}>
                    <span className={styles.roadmapGroupIcon}><SvgCheckCircle /></span>
                    Available now
                  </span>
                  <div className={styles.roadmapItems}>
                    {ROADMAP_DONE.map((item) => (
                      <div key={item} className={styles.roadmapItem}>
                        <span className={`${styles.roadmapCheck} ${styles.roadmapCheckDone}`}>
                          <SvgCheckCircle />
                        </span>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
                <div className={styles.roadmapGroup}>
                  <span className={`${styles.roadmapGroupLabel} ${styles.roadmapGroupLabelUpcoming}`}>
                    <span className={styles.roadmapGroupIcon}><SvgDiamond /></span>
                    Coming soon
                  </span>
                  <div className={styles.roadmapItems}>
                    {ROADMAP_UPCOMING.map((item) => (
                      <div key={item} className={styles.roadmapItem}>
                        <span className={`${styles.roadmapCheck} ${styles.roadmapCheckUpcoming}`}>
                          <SvgDiamond />
                        </span>
                        {item}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div
                ref={roadmapVisualRef}
                className={`${styles.roadmapVisual} ${roadmapVisualVisible ? styles.roadmapVisualVisible : ''}`}
              >
                <div className={styles.philosophyCard}>
                  <blockquote className={styles.philosophyQuote}>Built by students, for students.</blockquote>
                  <div className={styles.philosophyLines}>
                    <p className={styles.philosophyLine}>Most platforms focus on motivation. VYAS focuses on measurable improvement.</p>
                    <p className={styles.philosophyLine}>A good platform should not tell students what they want to hear. It should tell them what they need to know.</p>
                    <p className={styles.philosophyLine}>Data over guesswork. Clarity over comfort. Progress over perfection. Consistency over intensity.</p>
                  </div>
                  <div className={styles.philosophySignature}>
                    <div className={styles.philosophySigDot}>V</div>
                    <div className={styles.philosophySigText}>
                      <span className={styles.philosophySigName}>The VYAS Team</span>
                      <span className={styles.philosophySigRole}>Learn · Practice · Succeed</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* CTA BANNER */}
          <section className={styles.ctaBanner}>
            <div ref={ctaRef} className={`${styles.ctaInner} ${ctaVisible ? styles.ctaVisible : ''}`}>
              <div className={styles.ctaTextGroup}>
                <span className={styles.ctaKicker}>Your next improvement starts here</span>
                <h2 className={styles.ctaTitle}>Your Next Improvement Starts<br />With One Mock.</h2>
                <p className={styles.ctaSub}>
                  Join aspirants who choose precision over guesswork. Your first mock test is free — always.
                </p>
              </div>
              <div className={styles.ctaActions}>
                <button className={styles.ctaBtn} onClick={() => openModal('signup')}>Start Practising</button>
                <button className={styles.ctaBtn} onClick={() => openModal('signup')} style={{ background: 'rgba(17,17,17,0.6)' }}>Generate AI Mock</button>
                <button className={styles.ctaSecondaryBtn} onClick={() => openModal('login')}>Already a member? Sign in</button>
              </div>
            </div>
          </section>
        </main>

        {/* FOOTER */}
        <footer className={styles.footer}>
          <div className={styles.footerTop}>
            <div className={styles.footerBrand}>
              <div className={styles.footerBrandRow}>
                <VyasLogo variant="gold" size={30} />
                <span className={styles.footerBrandName}>VYAS</span>
              </div>
              <p className={styles.footerTagline}>AI-powered exam preparation platform. Intelligence · Discipline · Ascent.</p>
              <span className={styles.footerVersion}><span className={styles.footerVersionDot} />v2.0 · Actively maintained</span>
            </div>
            <div className={styles.footerCol}>
              <span className={styles.footerColTitle}>Platform</span>
              <Link href="/dashboard" className={styles.footerColLink}>Dashboard</Link>
              <Link href="/mocks"     className={styles.footerColLink}>Mock Tests</Link>
              <Link href="/ai-mock"   className={styles.footerColLink}>AI Generator</Link>
              <Link href="/wallet"    className={styles.footerColLink}>Wallet</Link>
            </div>
            <div className={styles.footerCol}>
              <span className={styles.footerColTitle}>Company</span>
              <Link href="/about"   className={styles.footerColLink}>About</Link>
              <Link href="/contact" className={styles.footerColLink}>Contact</Link>
            </div>
            <div className={styles.footerCol}>
              <span className={styles.footerColTitle}>Legal</span>
              <Link href="/privacy" className={styles.footerColLink}>Privacy Policy</Link>
              <Link href="/terms"   className={styles.footerColLink}>Terms &amp; Conditions</Link>
            </div>
            <div className={styles.footerCol}>
              <span className={styles.footerColTitle}>Support</span>
              <Link href="/contact" className={styles.footerColLink}>Help Centre</Link>
              <a href="mailto:support@vyasmock.online" className={styles.footerColLink}>Email Support</a>
              <Link href="/contact" className={styles.footerColLink}>Report a Bug</Link>
            </div>
          </div>
          <div className={styles.footerBottom}>
            <span className={styles.footerCopyright}>© {new Date().getFullYear()} VYAS. All rights reserved.</span>
            <nav className={styles.footerBottomLinks} aria-label="Footer legal links">
              <Link href="/privacy" className={styles.footerBottomLink}>Privacy</Link>
              <Link href="/terms"   className={styles.footerBottomLink}>Terms</Link>
              <Link href="/contact" className={styles.footerBottomLink}>Contact</Link>
            </nav>
          </div>
        </footer>

        {/* ── AUTH MODAL ──────────────────────────────────────────────── */}
        {modalOpen && (
          <div className={styles.overlay} onClick={closeModal}>
            <div className={styles.modal} onClick={(e) => e.stopPropagation()}>

              <div className={styles.modalHeader}>
                <div className={styles.modalBrand}><VyasLogo variant="gold" size={40} /><span>VYAS</span></div>
                <button className={styles.modalClose} onClick={closeModal} disabled={loading} aria-label="Close">
                  <SvgXClose />
                </button>
              </div>

              {/* OTP Screen */}
              {modalScreen === 'otp' ? (
                <div>
                  <div style={{ textAlign: 'center', marginBottom: '20px' }}>
                    <p style={{ fontSize: '14px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      We sent a 6-digit code to<br />
                      <strong style={{ color: 'var(--vyas-gold-light)' }}>{formData.email}</strong>
                    </p>
                    {otpSecondsLeft > 0 && (
                      <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
                        Expires in {formatCountdown(otpSecondsLeft)}
                      </p>
                    )}
                    {otpSecondsLeft === 0 && (
                      <p style={{ fontSize: '12px', color: 'var(--danger)', marginTop: '6px' }}>
                        Code expired — please resend
                      </p>
                    )}
                  </div>

                  <form className={styles.form} onSubmit={handleOTPSubmit} noValidate>
                    <div className={styles.field}>
                      <label className={styles.label} htmlFor="otp">Verification code</label>
                      <input
                        id="otp" name="otp" type="text" inputMode="numeric"
                        pattern="[0-9]{6}" maxLength={6} placeholder="123456"
                        className={styles.input} value={otpValue}
                        onChange={(e) => setOtpValue(e.target.value.replace(/\D/g, '').slice(0, 6))}
                        required autoFocus autoComplete="one-time-code" disabled={loading}
                        style={{ letterSpacing: '0.4em', fontSize: '22px', textAlign: 'center', fontFamily: 'var(--font-mono)' }}
                      />
                    </div>
                    {error && <p className={styles.formError}>{error}</p>}
                    <button type="submit" className={styles.submitBtn} disabled={loading || otpValue.length !== 6}>
                      {loading ? 'Verifying…' : 'Verify & create account'}
                    </button>
                  </form>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', justifyContent: 'center', marginTop: '16px' }}>
                    <button
                      onClick={handleResendOTP}
                      disabled={resendDisabled || loading}
                      style={{
                        border: 'none', background: 'transparent',
                        color: resendDisabled ? 'var(--text-muted)' : 'var(--vyas-gold-light)',
                        fontSize: '13px', fontWeight: 700,
                        cursor: resendDisabled ? 'default' : 'pointer',
                      }}
                    >Resend code</button>
                    <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>·</span>
                    <button
                      onClick={handleChangeEmail}
                      disabled={loading}
                      style={{
                        border: 'none', background: 'transparent',
                        color: 'var(--text-muted)', fontSize: '13px', cursor: 'pointer',
                      }}
                    >Change email</button>
                  </div>
                </div>

              ) : (
                <>
                  <div className={styles.tabs}>
                    <button
                      className={`${styles.tabBtn} ${tab === 'login' ? styles.activeTab : ''}`}
                      onClick={() => { setTab('login'); setError(''); setShowPassword(false) }}
                      disabled={loading}
                    >Sign in</button>
                    <button
                      className={`${styles.tabBtn} ${tab === 'signup' ? styles.activeTab : ''}`}
                      onClick={() => { setTab('signup'); setError(''); setShowPassword(false) }}
                      disabled={loading}
                    >Create account</button>
                  </div>

                  <button
                    type="button" onClick={handleGoogleAuth} disabled={loading}
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px',
                      width: '100%', minHeight: '44px', borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--surface-border)', background: 'var(--surface-2)',
                      color: 'var(--text-primary)', fontSize: '14px', fontWeight: 700,
                      cursor: 'pointer', transition: 'border-color 150ms', marginBottom: '4px',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(212,168,67,0.4)' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.borderColor = 'var(--surface-border)' }}
                  >
                    <SvgGoogle />
                    Continue with Google
                  </button>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: '4px 0' }}>
                    <div style={{ flex: 1, height: '1px', background: 'var(--surface-border)' }} />
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 700, letterSpacing: '0.06em' }}>OR</span>
                    <div style={{ flex: 1, height: '1px', background: 'var(--surface-border)' }} />
                  </div>

                  <form className={styles.form} onSubmit={handleSubmit} noValidate>
                    {tab === 'signup' && (
                      <div className={styles.field}>
                        <label className={styles.label} htmlFor="name">Full name</label>
                        <input
                          id="name" name="name" type="text" placeholder="Aditi Sharma"
                          className={styles.input} value={formData.name}
                          onChange={handleChange} required autoComplete="name" disabled={loading}
                        />
                      </div>
                    )}

                    <div className={styles.field}>
                      <label className={styles.label} htmlFor="email">Email</label>
                      <input
                        id="email" name="email" type="email" placeholder="you@example.com"
                        className={styles.input} value={formData.email}
                        onChange={handleChange} required autoComplete="email" disabled={loading}
                      />
                    </div>

                    <div className={styles.field}>
                      <label className={styles.label} htmlFor="password">Password</label>
                      <div style={{ position: 'relative' }}>
                        <input
                          id="password" name="password"
                          type={showPassword ? 'text' : 'password'}
                          placeholder={tab === 'signup' ? 'Min. 9 chars, A-Z, 1-9, @#!…' : 'Your password'}
                          className={styles.input}
                          value={formData.password}
                          onChange={handleChange}
                          required
                          autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                          disabled={loading}
                          style={{ paddingRight: '44px', width: '100%' }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword((v) => !v)}
                          aria-label={showPassword ? 'Hide password' : 'Show password'}
                          style={{
                            position: 'absolute', right: '12px', top: '50%',
                            transform: 'translateY(-50%)',
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: 'var(--text-muted)', display: 'flex', alignItems: 'center', padding: '4px',
                          }}
                        >
                          {showPassword ? <SvgEyeOff /> : <SvgEye />}
                        </button>
                      </div>
                      {tab === 'signup' && formData.password && (
                        <StrengthMeter password={formData.password} />
                      )}
                    </div>

                    {tab === 'login' && (
                      <p style={{ margin: '0', textAlign: 'right' }}>
                        <Link
                          href="/forgot-password"
                          style={{ fontSize: '12px', color: 'rgba(212,168,67,0.7)', textDecoration: 'none' }}
                          onClick={closeModal}
                        >Forgot password?</Link>
                      </p>
                    )}

                    {error && <p className={styles.formError}>{error}</p>}

                    <button
                      type="submit"
                      className={styles.submitBtn}
                      disabled={loading || (tab === 'signup' && !!formData.password && !pwStrength.isValid)}
                    >
                      {loading ? 'Please wait…' : tab === 'login' ? 'Sign in' : 'Continue'}
                    </button>

                    <p className={styles.consentText}>
                      By continuing, you agree to our{' '}
                      <Link href="/terms" className={styles.consentLink} onClick={closeModal}>Terms</Link>{' '}&amp;{' '}
                      <Link href="/privacy" className={styles.consentLink} onClick={closeModal}>Privacy Policy</Link>
                    </p>
                  </form>

                  <p className={styles.switchText}>
                    {tab === 'login' ? 'No account yet? ' : 'Already registered? '}
                    <button
                      className={styles.switchLink}
                      onClick={() => { setTab(tab === 'login' ? 'signup' : 'login'); setError(''); setShowPassword(false) }}
                      disabled={loading}
                    >
                      {tab === 'login' ? 'Create one' : 'Sign in'}
                    </button>
                  </p>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </>
  )
}