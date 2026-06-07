'use client'

/* eslint-disable @typescript-eslint/no-explicit-any */
/**
 * VYAS v2.0 — Dashboard (Next.js)
 *
 * v2.2.0 API path fixes:
 *   BUG: The previous version called non-existent paths via a local dashboardFetch helper:
 *     - /api/v1/analytics/me       → correct path is /analytics/me
 *     - /api/v1/analytics/attempts → this endpoint does NOT exist (was invented)
 *     - /api/v1/recommendations    → correct path is /recommendations
 *   All three called path mismatches caused 404s on every dashboard load after login,
 *   leaving the page in a perpetual error state despite auth working correctly.
 *
 *   FIX: Replaced the local dashboardFetch helper with the shared api.ts functions:
 *     - getAnalytics()        → GET /analytics/me
 *     - getMyAttempts()       → GET /users/me/attempts  (the correct attempts endpoint)
 *     - getRecommendations()  → GET /recommendations
 *   These are already defined and exported from lib/api.ts with correct paths,
 *   30s timeout, auth header injection, and typed return values.
 *   The local API_BASE + dashboardFetch block has been removed entirely.
 */

import { useState, useEffect, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import {
  Bar,
  CartesianGrid,
  Cell,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuthStore } from '@/stores/authStore'
import {
  isApiError,
  getAnalytics,
  getMyAttempts,
  getRecommendations,
  type Analytics,
  type Recommendations,
  type Attempt,
} from '@/lib/api'
import Navbar from '@/components/Navbar'
import DashboardSkeleton from '@/components/skeletons/DashboardSkeleton'
import WelcomePopupCarousel from '@/components/WelcomePopupCarousel'
import styles from '@/styles/Dashboard.module.css'
import dynamic from 'next/dynamic'

const LineChart = dynamic(() => import('recharts').then(mod => mod.LineChart), {
  ssr: false,
  loading: () => <div>Loading chart...</div>,
})

const BarChart = dynamic(() => import('recharts').then(mod => mod.BarChart), {
  ssr: false,
  loading: () => <div>Loading chart...</div>,
})

/* ─── Helper Components ──────────────────────────────────────────────────────── */

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  tone?: 'gold' | 'blue' | 'green'
}

function StatCard({ label, value, sub, tone = 'gold' }: StatCardProps) {
  return (
    <div className={styles.statCard} data-tone={tone}>
      <p className={styles.statLabel}>{label}</p>
      <p className={styles.statValue}>{value}</p>
      {sub && <p className={styles.statSub}>{sub}</p>}
    </div>
  )
}

function fmt(seconds: number | null | undefined) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

function scoreColor(pct: number) {
  if (pct >= 70) return 'var(--success)'
  if (pct >= 40) return 'var(--warning)'
  return 'var(--danger)'
}

interface AttemptsTableProps {
  rows: any[]
  navigate: (path: string) => void
  isAI?: boolean
}

function AttemptsTable({ rows, navigate, isAI = false }: AttemptsTableProps) {
  return (
    <div className={styles.tableWrapper}>
      <table className={styles.table}>
        <thead>
          <tr>
            <th>Paper</th>
            <th>{isAI ? 'Difficulty' : 'Year'}</th>
            <th>Score</th>
            <th>Accuracy</th>
            <th>Time</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((attempt) => {
            const pct = attempt.total_marks ? ((attempt.score / attempt.total_marks) * 100).toFixed(1) : null
            return (
              <tr key={attempt.attempt_id}>
                <td className={styles.paperCell}>
                  {isAI && <span className={styles.aiBadgeInline}>✦ </span>}
                  {attempt.subject}
                </td>
                <td>{attempt.year || '-'}</td>
                <td>
                  {pct != null ? (
                    <span className={styles.scoreBadge} style={{ color: scoreColor(parseFloat(pct)) }}>
                      {attempt.score}/{attempt.total_marks} ({pct}%)
                    </span>
                  ) : (
                    '-'
                  )}
                </td>
                <td>{attempt.accuracy != null ? `${attempt.accuracy.toFixed(1)}%` : '-'}</td>
                <td>{fmt(attempt.time_taken_seconds)}</td>
                <td>
                  <span className={attempt.submitted ? styles.badgeDone : styles.badgePending}>
                    {attempt.submitted ? 'Submitted' : 'In progress'}
                  </span>
                </td>
                <td>
                  {attempt.submitted && (
                    <button className={styles.viewBtn} onClick={() => navigate(`/results/${attempt.attempt_id}`)}>
                      View results
                    </button>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

/* ─── Main Component ──────────────────────────────────────────────────────────── */

export default function Dashboard() {
  const { user, sessionChecked, isAuthenticated } = useAuthStore()
  const router = useRouter()

  const [analytics, setAnalytics] = useState<Analytics | null>(null)
  const [attempts, setAttempts] = useState<any[]>([])
  const [recommendations, setRecommendations] = useState<Recommendations | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!sessionChecked) return
    if (!isAuthenticated) {
      router.push('/')
      return
    }

    let mounted = true
    ;(async () => {
      try {
        // BUG FIX v2.2.0: replaced wrong dashboardFetch('/api/v1/...') calls with
        // the shared api.ts functions that use the correct backend paths:
        //   getAnalytics()       → GET /analytics/me
        //   getMyAttempts()      → GET /users/me/attempts
        //   getRecommendations() → GET /recommendations
        const [ana, att, rec] = await Promise.all([
          getAnalytics(),
          getMyAttempts(),
          getRecommendations(),
        ])
        if (mounted) {
          setAnalytics(ana)
          setAttempts(att as any[])
          setRecommendations(rec)
        }
      } catch (e: unknown) {
        if (mounted) {
          setError(isApiError(e) ? e.message : 'Failed to load dashboard data.')
        }
      } finally {
        if (mounted) setLoading(false)
      }
    })()
    return () => {
      mounted = false
    }
  }, [sessionChecked, isAuthenticated, router])

  const trendData = useMemo(() => {
    return [...attempts]
      .filter((attempt) => attempt.submitted && attempt.total_marks)
      .reverse()
      .map((attempt, index) => ({
        label: `A${index + 1}`,
        score: Number(((attempt.score / attempt.total_marks) * 100).toFixed(1)),
        accuracy: Number((attempt.accuracy || 0).toFixed(1)),
      }))
  }, [attempts])

  const topicData = useMemo(() => {
    return (analytics?.topic_mastery || [])
      .slice()
      .sort((a: any, b: any) => b.total - a.total)
      .slice(0, 8)
      .map((topic: any) => ({
        name: topic.topic.length > 18 ? `${topic.topic.slice(0, 18)}...` : topic.topic,
        accuracy: topic.accuracy,
        fill: scoreColor(topic.accuracy),
      }))
  }, [analytics])

  const navigate = (path: string) => router.push(path)

  return (
    <div className={styles.page}>
      <WelcomePopupCarousel />

      <Navbar />
      <main className={styles.main}>
        <section className={styles.welcome}>
          <div>
            <span className={styles.kicker}>Performance command</span>
            <h1 className={styles.welcomeTitle}>Welcome back, {user?.name?.split(' ')[0]}</h1>
            <p className={styles.welcomeSub}>Your preparation signal, pace, and mastery in one place.</p>
          </div>
          <button className={styles.startBtn} onClick={() => navigate('/mocks')}>
            Start a mock test →
          </button>
        </section>

        {loading && <DashboardSkeleton />}

        {error && !loading && (
          <div className={styles.errorBox}>
            <p>{error}</p>
            <button onClick={() => window.location.reload()}>Retry</button>
          </div>
        )}

        {!loading && !error && analytics && (
          <>
            <section className={styles.statsRow}>
              <StatCard label="Total attempts" value={analytics.total_attempts} sub="Completed and active sessions" />
              <StatCard
                label="Avg score"
                value={`${analytics.avg_score_percentage?.toFixed(1) ?? '-'}%`}
                sub="Across submitted attempts"
                tone="blue"
              />
              <StatCard
                label="Avg accuracy"
                value={`${analytics.avg_accuracy?.toFixed(1) ?? '-'}%`}
                sub="Correct among attempted"
                tone="green"
              />
              {recommendations && (analytics.total_attempts > 0 || recommendations.has_proficiency_data) && (
                <StatCard
                  label="VYAS Level"
                  value={recommendations.overall_level ?? '-'}
                  sub={
                    recommendations.total_signals > 0
                      ? `ELO ${(recommendations.overall_score ?? 0).toFixed(0)} · ${recommendations.total_signals} signal${
                          recommendations.total_signals !== 1 ? 's' : ''
                        }`
                      : 'Complete attempts to build your rank'
                  }
                  tone="gold"
                />
              )}
            </section>

            {recommendations?.onboarding_card && (
              <div className={styles.coldStartBox}>
                <span className={styles.vyasGlyph}>✦</span>
                <div>
                  <span className={styles.aiSuggTitle}>{recommendations.onboarding_card.title}</span>
                  <span className={styles.aiSuggDesc}>{recommendations.onboarding_card.message}</span>
                </div>
                <button className={styles.aiSuggBtn} onClick={() => navigate(recommendations.onboarding_card!.cta_url)}>
                  {recommendations.onboarding_card.cta}
                </button>
              </div>
            )}

            {recommendations?.has_proficiency_data && recommendations.weak_topics.length > 0 && (
              <section className={styles.section}>
                <div className={styles.sectionHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>⚠ Topics needing attention</h2>
                    <p className={styles.sectionSub}>
                      Areas where your accuracy is below 50% — focus here for the biggest gains.
                    </p>
                  </div>
                  <button className={styles.browseLink} onClick={() => navigate('/ai-mock')}>
                    Practice with AI →
                  </button>
                </div>
                <div className={styles.weakTopicsGrid}>
                  {recommendations.weak_topics.map((t) => (
                    <div key={`${t.subject}-${t.topic}`} className={styles.weakCard}>
                      <div className={styles.weakSubject}>{t.subject}</div>
                      <div className={styles.weakTopic}>{t.topic}</div>
                      <div className={styles.weakAccRow}>
                        <div className={styles.weakBar} style={{ width: `${Math.min(100, t.proficiency ?? 0)}%` }} />
                        <span className={styles.weakPct}>{(t.proficiency ?? 0).toFixed(0)}</span>
                      </div>
                      <div className={styles.weakCount}>{t.level}</div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {recommendations?.recommended_mocks?.length > 0 && (
              <section className={styles.section}>
                <div className={styles.sectionHeader}>
                  <div>
                    <h2 className={styles.sectionTitle}>✦ Recommended for you</h2>
                    <p className={styles.sectionSub}>
                      Papers selected based on your proficiency profile.
                    </p>
                  </div>
                  <button className={styles.browseLink} onClick={() => navigate('/mocks')}>
                    Browse all →
                  </button>
                </div>
                <div className={styles.recGrid}>
                  {recommendations.recommended_mocks.map((m) => (
                    <div key={m.id} className={styles.recCard}>
                      <div className={styles.recCardTop}>
                        <span className={styles.recExam}>{m.exam}</span>
                        {m.is_ai_generated && <span className={styles.aiBadgeInline}>✦ AI</span>}
                        <span className={styles.recMeta}>
                          {m.question_count}q · {m.duration_minutes}m
                        </span>
                      </div>
                      <div className={styles.recSubject}>{m.subject}</div>
                      <div className={styles.recYear}>{m.year}</div>
                      <button className={styles.recBtn} onClick={() => navigate('/mocks')}>
                        Start test →
                      </button>
                    </div>
                  ))}
                </div>

                {recommendations.ai_mock_suggestion && (
                  <div className={styles.aiSuggestionBox}>
                    <div className={styles.aiSuggLeft}>
                      <span className={styles.aiSuggGlyph}>✦</span>
                      <div>
                        <span className={styles.aiSuggTitle}>AI Mock Suggestion</span>
                        <span className={styles.aiSuggDesc}>{recommendations.ai_mock_suggestion.reason}</span>
                      </div>
                    </div>
                    <button className={styles.aiSuggBtn} onClick={() => navigate('/ai-mock')}>
                      Generate now →
                    </button>
                  </div>
                )}
              </section>
            )}

            {recommendations &&
              !recommendations.has_proficiency_data &&
              attempts.length > 0 &&
              !recommendations.onboarding_card && (
                <div className={styles.coldStartBox}>
                  <span className={styles.aiSuggGlyph}>✦</span>
                  <div>
                    <span className={styles.aiSuggTitle}>Your VYAS profile is building</span>
                    <span className={styles.aiSuggDesc}>
                      Your proficiency profile processes in the background after each submission. Submit 3+ mock tests to
                      unlock fully personalised recommendations and your VYAS rank.
                    </span>
                  </div>
                </div>
              )}

            <section className={styles.chartGrid}>
              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <div>
                    <h2 className={styles.panelTitle}>Score trajectory</h2>
                    <p className={styles.panelSub}>Score percentage over submitted attempts</p>
                  </div>
                </div>
                <div className={styles.chartBox}>
                  {trendData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={trendData}>
                        <CartesianGrid stroke="rgba(212,168,67,0.08)" vertical={false} />
                        <XAxis dataKey="label" stroke="#9a9080" tickLine={false} axisLine={false} />
                        <YAxis stroke="#9a9080" tickLine={false} axisLine={false} domain={[0, 100]} />
                        <Tooltip
                          contentStyle={{ background: '#111', border: '1px solid #2a2a2a', borderRadius: 12 }}
                        />
                        <Line
                          type="monotone"
                          dataKey="score"
                          stroke="#d4a843"
                          strokeWidth={3}
                          dot={{ r: 4, fill: '#d4a843' }}
                        />
                        <Line type="monotone" dataKey="accuracy" stroke="#3b82f6" strokeWidth={2} dot={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className={styles.emptyChart}>Complete a mock to unlock your score line.</div>
                  )}
                </div>
              </div>

              <div className={styles.panel}>
                <div className={styles.panelHeader}>
                  <div>
                    <h2 className={styles.panelTitle}>Topic mastery</h2>
                    <p className={styles.panelSub}>Green 70%+, amber 40-70%, red below 40%</p>
                  </div>
                </div>
                <div className={styles.chartBox}>
                  {topicData.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={topicData} layout="vertical" margin={{ left: 12, right: 20 }}>
                        <CartesianGrid stroke="rgba(212,168,67,0.08)" horizontal={false} />
                        <XAxis type="number" domain={[0, 100]} stroke="#9a9080" tickLine={false} axisLine={false} />
                        <YAxis
                          dataKey="name"
                          type="category"
                          stroke="#9a9080"
                          tickLine={false}
                          axisLine={false}
                          width={116}
                        />
                        <Tooltip
                          contentStyle={{ background: '#111', border: '1px solid #2a2a2a', borderRadius: 12 }}
                        />
                        <Bar dataKey="accuracy" radius={[0, 8, 8, 0]}>
                          {topicData.map((entry: any) => (
                            <Cell key={entry.name} fill={entry.fill} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className={styles.emptyChart}>Topic mastery appears after submissions.</div>
                  )}
                </div>
              </div>
            </section>

            <section className={styles.section}>
              <div className={styles.sectionHeader}>
                <div>
                  <h2 className={styles.sectionTitle}>Recent attempts</h2>
                  <p className={styles.sectionSub}>Continue reviewing what you have already earned.</p>
                </div>
                <button className={styles.browseLink} onClick={() => navigate('/mocks')}>
                  Browse papers →
                </button>
              </div>

              {attempts.length === 0 ? (
                <div className={styles.emptyState}>
                  <p className={styles.emptyTitle}>No attempts yet</p>
                  <p className={styles.emptySub}>Take your first mock test and your results will appear here.</p>
                  <button className={styles.startBtn} onClick={() => navigate('/mocks')}>
                    Browse mock tests →
                  </button>
                </div>
              ) : (
                <>
                  {attempts.filter((a) => !a.is_ai_generated).length > 0 && (
                    <AttemptsTable rows={attempts.filter((a) => !a.is_ai_generated)} navigate={navigate} />
                  )}

                  {attempts.filter((a) => a.is_ai_generated).length > 0 && (
                    <>
                      <div className={styles.attemptsSubheader}>
                        <span className={styles.vyasGlyph}>✦</span>
                        <span>AI-generated mocks</span>
                        <button
                          className={styles.browseLink}
                          style={{ marginLeft: 'auto' }}
                          onClick={() => navigate('/ai-mock')}
                        >
                          Generate new →
                        </button>
                      </div>
                      <AttemptsTable rows={attempts.filter((a) => a.is_ai_generated)} navigate={navigate} isAI />
                    </>
                  )}
                </>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}