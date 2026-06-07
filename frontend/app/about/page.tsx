import Link from 'next/link'
import type { Metadata } from 'next'
import StaticLayout from '@/components/Staticlayout'
import styles from '@/styles/StaticPage.module.css'

export const metadata: Metadata = {
  title: 'About — VYAS',
  description:
    'Built for serious aspirants. VYAS is an AI-powered exam preparation platform that turns every mock test into a performance intelligence report.',
}

/* ── SVG icon components ──────────────────────────────────────────────────── */
const IconTarget = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="26" height="26" aria-hidden="true">
    <circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" />
  </svg>
)
const IconTelescope = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="26" height="26" aria-hidden="true">
    <circle cx="12" cy="12" r="2" /><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
  </svg>
)
const IconCpu = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <rect x="4" y="4" width="16" height="16" rx="2" /><rect x="9" y="9" width="6" height="6" />
    <path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2" />
  </svg>
)
const IconBarChart = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <line x1="18" y1="20" x2="18" y2="10" /><line x1="12" y1="20" x2="12" y2="4" /><line x1="6" y1="20" x2="6" y2="14" /><line x1="2" y1="20" x2="22" y2="20" />
  </svg>
)
const IconTrendUp = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" /><polyline points="16 7 22 7 22 13" />
  </svg>
)
const IconSearch = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
  </svg>
)
const IconRefresh = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <polyline points="23 4 23 10 17 10" /><polyline points="1 20 1 14 7 14" />
    <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
  </svg>
)
const IconWallet = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" width="22" height="22" aria-hidden="true">
    <path d="M20 12V8H6a2 2 0 01-2-2c0-1.1.9-2 2-2h12v4" /><path d="M4 6v12c0 1.1.9 2 2 2h14v-4" />
    <circle cx="16" cy="14" r="1" />
  </svg>
)

const FEATURES = [
  { icon: <IconCpu />, title: 'AI Mock Generation', desc: 'Fresh, exam-relevant questions generated on demand — calibrated to your level and focused on your weakest areas.' },
  { icon: <IconBarChart />, title: 'Deep Analytics', desc: 'Every attempt produces a breakdown by topic, accuracy, time distribution, and cross-attempt trends.' },
  { icon: <IconTrendUp />, title: 'Performance Tracking', desc: 'Improvement becomes visible over weeks and months. Every attempt is stored and compared against your history.' },
  { icon: <IconSearch />, title: 'Question Intelligence', desc: 'Question-level review with correct answer breakdowns, detailed explanations, and behaviour signals.' },
  { icon: <IconRefresh />, title: 'Learning Feedback Loops', desc: 'Each attempt informs the next. Your weak areas are surfaced automatically so every session has direction.' },
  { icon: <IconWallet />, title: 'Fair Credit System', desc: 'Transparent wallet — know exactly what each feature costs. No hidden charges, no confusion.' },
]

export default function AboutPage() {
  return (
    <StaticLayout>
      {/* Hero */}
      <div className={styles.pageHero}>
        <span className={styles.kicker}>About VYAS</span>
        <h1 className={styles.pageTitle}>The Story Behind VYAS</h1>
        <p className={styles.pageLead}>
          Built to make exam preparation measurable. Our mission: help students improve through structured,
          data-driven practice — not hopeful repetition.
        </p>
      </div>

      {/* Mission + Vision */}
      <div className={styles.missionGrid}>
        <div className={styles.missionCard}>
          <div className={styles.missionIconWrap}>
            <IconTarget />
          </div>
          <h3 className={styles.missionTitle}>Mission</h3>
          <p className={styles.missionDesc}>
            Help every student improve through data-driven practice — not by giving them more questions,
            but by helping them understand the ones they already have.
          </p>
        </div>
        <div className={styles.missionCard}>
          <div className={styles.missionIconWrap}>
            <IconTelescope />
          </div>
          <h3 className={styles.missionTitle}>Vision</h3>
          <p className={styles.missionDesc}>
            Build the most intelligent exam preparation ecosystem in India — where every student has
            access to the kind of honest, structured feedback a great tutor would provide.
          </p>
        </div>
      </div>

      {/* Stats */}
      <div className={styles.statRow}>
        <div className={styles.statCard}>
          <span className={styles.statNum}>1000+</span>
          <span className={styles.statLabel}>Mocks Generated</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statNum}>5000+</span>
          <span className={styles.statLabel}>Questions Attempted</span>
        </div>
        <div className={styles.statCard}>
          <span className={styles.statNum}>50+</span>
          <span className={styles.statLabel}>Subjects Covered</span>
        </div>
      </div>

      <hr className={styles.divider} />

      {/* Why we built VYAS */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Why We Built VYAS</h2>
        <p>
          Most practice tools hand you a score and move on. You finish a mock test, see 68%, and have
          no clear sense of whether that means you misread questions, ran out of time, or simply don&apos;t
          know the topic.
        </p>
        <p>
          VYAS treats every attempt as structured data. Each submission produces a breakdown by topic,
          accuracy, time distribution, and cross-attempt trends — so progress becomes visible and your
          next session has a clear direction.
        </p>
        <p>
          We built VYAS because we wanted to understand performance, not just be told a number.
          Understanding leads to improvement. A number just leads to anxiety.
        </p>
      </div>

      {/* What makes VYAS different */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>What Makes VYAS Different</h2>
        <div className={styles.featureListGrid}>
          {FEATURES.map((f) => (
            <div key={f.title} className={styles.featureListCard}>
              <div className={styles.featureListIconWrap}>{f.icon}</div>
              <div>
                <h4 className={styles.featureListTitle}>{f.title}</h4>
                <p className={styles.featureListDesc}>{f.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Core principles */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Core Principles</h2>
        <div className={styles.principlesGrid}>
          {[
            { principle: 'Clarity over motivation', desc: 'Tell students what they need to know, not what they want to hear.' },
            { principle: 'Data over guesswork', desc: 'Every insight is grounded in real attempt data, not assumptions.' },
            { principle: 'Progress over perfection', desc: 'Improvement is measured in trajectory, not in perfect scores.' },
            { principle: 'Consistency over intensity', desc: 'Regular structured practice beats occasional cramming every time.' },
          ].map((p) => (
            <div key={p.principle} className={styles.principleCard}>
              <span className={styles.principleText}>{p.principle}</span>
              <p className={styles.principleDesc}>{p.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Growth Timeline */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Where We&apos;ve Been. Where We&apos;re Headed.</h2>
        <div className={styles.timeline}>
          <div className={styles.timelineItem}>
            <div className={styles.timelineDot} />
            <div className={styles.timelineContent}>
              <span className={styles.timelineLabel}>V1 — Foundation</span>
              <p className={styles.timelineDesc}>
                Basic mock tests, question bank, and simple results view. The core loop established.
              </p>
            </div>
          </div>
          <div className={styles.timelineItem}>
            <div className={`${styles.timelineDot} ${styles.timelineDotActive}`} />
            <div className={styles.timelineContent}>
              <span className={`${styles.timelineLabel} ${styles.timelineLabelActive}`}>
                V2 — AI-Powered Platform (Current)
              </span>
              <p className={styles.timelineDesc}>
                Full analytics dashboard, AI Mock Generator, wallet and credit system, topic mastery
                tracking, and complete performance intelligence after every attempt.
              </p>
            </div>
          </div>
          <div className={styles.timelineItem}>
            <div className={`${styles.timelineDot} ${styles.timelineDotFuture}`} />
            <div className={styles.timelineContent}>
              <span className={`${styles.timelineLabel} ${styles.timelineLabelFuture}`}>
                V3 — Complete Learning Ecosystem
              </span>
              <p className={styles.timelineDesc}>
                Study Planner, AI Mentor, Personalized Learning Paths, and Smart Revision System.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Current coverage */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Current Coverage</h2>
        <ul>
          <li>CUET — Economics, English, General Test</li>
          <li>GATE — DBMS, Operating Systems</li>
          <li>AI-generated mocks across custom topics</li>
          <li>More subjects and exams added regularly</li>
        </ul>
        <p>
          Questions are sourced from publicly available past papers published by their respective
          conducting bodies. Coverage expands based on demand and community feedback.
        </p>
      </div>

      <hr className={styles.divider} />

      <div className={styles.infoCard}>
        <p>
          Have a question, spotted an error in a question, or want to suggest a subject?{' '}
          <Link href="/contact">Get in touch</Link> — we read and respond to everything.
        </p>
      </div>
    </StaticLayout>
  )
}
