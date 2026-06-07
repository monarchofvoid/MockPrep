'use client'

/**
 * VYAS v2.0 — Wallet Page
 * ========================
 * Displays the user's credit wallet:
 *   - Current balance (credits + microcredits)
 *   - Lifetime earned / spent summary
 *   - Paginated transaction history with entry type badges
 *   - Quick link to the /purchase page
 *
 * API calls:
 *   GET /api/v1/wallet/me      → balance + recent transactions
 *   GET /api/v1/wallet/history → paginated full history (on "Load more")
 */

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Navbar from '@/components/Navbar'
import { useAuthStore } from '@/stores/authStore'
import { getWallet, getTransactions, type WalletResponse, type WalletTransaction } from '@/lib/api'

// Type aliases matching the names used throughout this file
type LedgerEntry = WalletTransaction
type WalletState = WalletResponse
import styles from '@/styles/Wallet.module.css'

// ── Helpers ───────────────────────────────────────────────────────────────────

const ENTRY_TYPE_LABELS: Record<string, { label: string; tone: 'credit' | 'debit' | 'neutral' }> = {
  SIGNUP_BONUS:          { label: 'Welcome Bonus',      tone: 'credit'  },
  PURCHASE:              { label: 'Credit Purchase',    tone: 'credit'  },
  MOCK_DEDUCTION:        { label: 'AI Mock',            tone: 'debit'   },
  TUTOR_DEDUCTION:       { label: 'VYAS Explain',       tone: 'debit'   },
  ADMIN_GRANT:           { label: 'Admin Grant',        tone: 'credit'  },
  REFUND:                { label: 'Refund',             tone: 'credit'  },
  SUBSCRIPTION_CREDIT:   { label: 'Subscription',       tone: 'credit'  },
  REFERRAL_BONUS:        { label: 'Referral Bonus',     tone: 'credit'  },
  COUPON_CREDIT:         { label: 'Coupon',             tone: 'credit'  },
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatMicrocredits(mc: number): string {
  const credits = mc / 100
  const sign = mc >= 0 ? '+' : ''
  return `${sign}${credits.toFixed(2)}`
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function BalanceCard({
  balanceCredits,
  balanceMicro,
  lifetimeEarned,
  lifetimeSpent,
  lowCreditWarning,
}: {
  balanceCredits: number
  balanceMicro: number
  lifetimeEarned: number
  lifetimeSpent: number
  lowCreditWarning: boolean
}) {
  return (
    <div className={styles.balanceCard}>
      <div className={styles.balanceHeader}>
        <span className={styles.balanceLabel}>Current Balance</span>
        {lowCreditWarning && (
          <span className={styles.lowCreditBadge}>Low Credits</span>
        )}
      </div>
      <div className={styles.balanceAmount}>
        <span className={styles.balanceCredits}>{balanceCredits.toFixed(2)}</span>
        <span className={styles.balanceCreditLabel}>credits</span>
      </div>
      <div className={styles.balanceMicro}>{balanceMicro} microcredits</div>

      <div className={styles.balanceStats}>
        <div className={styles.balanceStat}>
          <span className={styles.statStatLabel}>Total Earned</span>
          <span className={styles.statValue + ' ' + styles.earned}>
            +{(lifetimeEarned / 100).toFixed(2)}
          </span>
        </div>
        <div className={styles.balanceDivider} />
        <div className={styles.balanceStat}>
          <span className={styles.statStatLabel}>Total Spent</span>
          <span className={styles.statValue + ' ' + styles.spent}>
            {(lifetimeSpent / 100).toFixed(2)}
          </span>
        </div>
      </div>

      {lowCreditWarning && (
        <div className={styles.topUpPrompt}>
          <p>Running low on credits — top up to keep learning.</p>
          <Link href="/purchase" className={styles.topUpBtn}>
            Buy Credits →
          </Link>
        </div>
      )}
    </div>
  )
}

function TransactionRow({ entry }: { entry: LedgerEntry }) {
  const typeInfo = ENTRY_TYPE_LABELS[entry.entry_type] ?? {
    label: entry.entry_type.replace(/_/g, ' '),
    tone: entry.amount_microcredits >= 0 ? 'credit' : 'debit',
  }

  return (
    <div className={styles.txRow}>
      <div className={styles.txLeft}>
        <span className={`${styles.txBadge} ${styles[typeInfo.tone]}`}>
          {typeInfo.label}
        </span>
        <span className={styles.txDesc}>
          {entry.description || '—'}
        </span>
        <span className={styles.txDate}>{formatDate(entry.created_at)}</span>
      </div>
      <div className={styles.txRight}>
        <span className={`${styles.txAmount} ${entry.amount_microcredits >= 0 ? styles.credit : styles.debit}`}>
          {formatMicrocredits(entry.amount_microcredits)}
        </span>
        <span className={styles.txBalance}>
          bal: {(entry.balance_after_microcredits / 100).toFixed(2)}
        </span>
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function WalletPage() {
  const router = useRouter()
  const { user, isAuthenticated, sessionChecked } = useAuthStore()
  const [wallet, setWallet] = useState<WalletState | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [allEntries, setAllEntries] = useState<LedgerEntry[]>([])

  // ── Auth guard ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      router.push('/?from=/wallet')
    }
  }, [sessionChecked, isAuthenticated, router])

  // ── Initial load ───────────────────────────────────────────────────────────
  const loadWallet = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const data = await getWallet()
      setWallet(data)
      setAllEntries(data.recent_transactions ?? [])
      // If fewer than 20 returned in initial load, no more pages
      setHasMore((data.recent_transactions?.length ?? 0) >= 20)
    } catch {
      setError('Failed to load wallet. Please refresh.')
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (isAuthenticated) loadWallet()
  }, [isAuthenticated, loadWallet])

  // ── Pagination ─────────────────────────────────────────────────────────────
  const loadMore = async () => {
    if (loadingMore || !hasMore) return
    setLoadingMore(true)
    try {
      const nextPage = page + 1
      const data = await getTransactions({ page: nextPage, per_page: 20 })
      const newEntries = data.transactions ?? []
      setAllEntries(prev => [...prev, ...newEntries])
      setPage(nextPage)
      setHasMore(newEntries.length >= 20)
    } catch {
      // Silently fail pagination — user can retry
    } finally {
      setLoadingMore(false)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  if (!sessionChecked || (sessionChecked && !isAuthenticated)) {
    return null // middleware handles redirect
  }

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.header}>
          <h1 className={styles.title}>My Wallet</h1>
          <Link href="/purchase" className={styles.buyBtn}>
            + Buy Credits
          </Link>
        </div>

        {isLoading && (
          <div className={styles.loadingState}>
            <div className={styles.spinner} />
            <p>Loading wallet…</p>
          </div>
        )}

        {error && (
          <div className={styles.errorState}>
            <p>{error}</p>
            <button onClick={loadWallet} className={styles.retryBtn}>Retry</button>
          </div>
        )}

        {!isLoading && wallet && (
          <>
            <BalanceCard
              balanceCredits={wallet.balance_credits}
              balanceMicro={wallet.balance_microcredits}
              lifetimeEarned={wallet.lifetime_earned_credits * 100}
              lifetimeSpent={wallet.lifetime_spent_credits * 100}
              lowCreditWarning={user?.low_credit_warning ?? false}
            />

            <section className={styles.historySection}>
              <h2 className={styles.sectionTitle}>Transaction History</h2>

              {allEntries.length === 0 ? (
                <div className={styles.emptyState}>
                  <p>No transactions yet.</p>
                  <p>Start by generating an AI mock test or purchasing credits.</p>
                </div>
              ) : (
                <div className={styles.txList}>
                  {allEntries.map(entry => (
                    <TransactionRow key={entry.id} entry={entry} />
                  ))}
                </div>
              )}

              {hasMore && (
                <button
                  className={styles.loadMoreBtn}
                  onClick={loadMore}
                  disabled={loadingMore}
                >
                  {loadingMore ? 'Loading…' : 'Load More'}
                </button>
              )}
            </section>
          </>
        )}
      </main>
    </div>
  )
}