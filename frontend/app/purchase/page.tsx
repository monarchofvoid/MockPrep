'use client'

/**
 * VYAS v2.0 — Purchase / Plans Page
 * ====================================
 * The complete credit purchase flow:
 *   1. List credit plans from API (GET /api/v1/payments/plans)
 *   2. User selects a plan
 *   3. Create a Razorpay order (POST /api/v1/payments/create-order)
 *   4. Load Razorpay.js checkout modal
 *   5. On modal success → verify payment server-side (POST /api/v1/payments/verify)
 *   6. Poll order status (GET /api/v1/payments/status/:orderId) until settled
 *   7. Show success or failure state, update wallet balance in Zustand store
 *
 * Security note: Credits are ONLY granted server-side via the Razorpay webhook.
 * The client-side verify call records the payment event, but the webhook is the
 * authoritative credit-granting path. The polling UI shows the user that we
 * received the payment while the webhook processes.
 *
 * Razorpay.js is loaded dynamically and only when the user initiates checkout.
 * This keeps the initial page load fast and avoids loading the SDK on every visit.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Navbar from '@/components/Navbar'
import { useAuthStore } from '@/stores/authStore'
import {
  getCreditPlans,
  createPaymentOrder,
  verifyPayment,
  getPaymentStatus,
  type CreditPlan,
  type PaymentOrder,
  type PaymentStatus,
} from '@/lib/api'
import styles from '@/styles/Purchase.module.css'

// ── Razorpay types ─────────────────────────────────────────────────────────────
declare global {
  interface Window {
    Razorpay: new (options: RazorpayOptions) => RazorpayInstance
  }
}

interface RazorpayOptions {
  key: string
  order_id: string
  amount: number
  currency: string
  name: string
  description: string
  image?: string
  prefill?: { name?: string; email?: string; contact?: string }
  theme?: { color?: string }
  modal?: { ondismiss?: () => void }
  config?: {
    display?: {
      hide?: { method: string; flows?: string[] }[]
      preferences?: { show_default_blocks?: boolean }
    }
  }
  handler: (response: RazorpaySuccessResponse) => void
}

interface RazorpayInstance {
  open: () => void
  on: (event: string, handler: () => void) => void
}

interface RazorpaySuccessResponse {
  razorpay_order_id: string
  razorpay_payment_id: string
  razorpay_signature: string
}

// ── Constants ─────────────────────────────────────────────────────────────────
const POLL_INTERVAL_MS = 2000
const POLL_MAX_ATTEMPTS = 20 // 40 seconds total

// ── Helpers ───────────────────────────────────────────────────────────────────

// ── Device detection ──────────────────────────────────────────────────────────
// Used to hide UPI intent tiles (Google Pay / PhonePe) on desktop, where
// they don't work. On mobile the full default UI is shown.
function isMobileDevice(): boolean {
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i
    .test(navigator.userAgent)
}

function loadRazorpayScript(): Promise<boolean> {
  return new Promise(resolve => {
    if (window.Razorpay) return resolve(true)
    const script = document.createElement('script')
    script.src = 'https://checkout.razorpay.com/v1/checkout.js'
    script.onload = () => resolve(true)
    script.onerror = () => resolve(false)
    document.head.appendChild(script)
  })
}

// ── Subcomponents ─────────────────────────────────────────────────────────────

function PlanCard({
  plan,
  isSelected,
  isLoading,
  onSelect,
}: {
  plan: CreditPlan
  isSelected: boolean
  isLoading: boolean
  onSelect: (plan: CreditPlan) => void
}) {
  return (
    <div
      className={`${styles.planCard} ${isSelected ? styles.planSelected : ''} ${plan.is_popular ? styles.planPopular : ''}`}
      onClick={() => !isLoading && onSelect(plan)}
      role="button"
      tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && !isLoading && onSelect(plan)}
    >
      {plan.is_popular && (
        <div className={styles.popularBadge}>Most Popular</div>
      )}
      <h3 className={styles.planName}>{plan.name}</h3>
      {plan.description && (
        <p className={styles.planDesc}>{plan.description}</p>
      )}
      <div className={styles.planCredits}>
        <span className={styles.creditsNum}>{plan.credits_granted}</span>
        <span className={styles.creditsUnit}>credits</span>
      </div>
      <div className={styles.planPrice}>
        <span className={styles.priceSymbol}>₹</span>
        <span className={styles.priceAmount}>{plan.amount_inr}</span>
      </div>
      <div className={styles.pricePerCredit}>
        ₹{(plan.amount_inr / plan.credits_granted).toFixed(2)} per credit
      </div>
      <button
        className={`${styles.selectBtn} ${isSelected ? styles.selectBtnActive : ''}`}
        disabled={isLoading}
        onClick={e => { e.stopPropagation(); if (!isLoading) onSelect(plan) }}
      >
        {isSelected && isLoading ? 'Processing…' : 'Buy Now'}
      </button>
    </div>
  )
}

function PollingStatus({
  status,
  creditsGranted,
  onDone,
}: {
  status: PaymentStatus | null
  creditsGranted: number
  onDone: () => void
}) {
  const statusLabel: Record<string, string> = {
    created:   'Order created',
    initiated: 'Payment initiated',
    verified:  'Payment verified — crediting wallet…',
    settled:   '✓ Credits added to your wallet!',
    failed:    '✗ Payment failed',
    refunded:  'Refunded',
  }

  const settled = status?.status === 'settled'
  const failed  = status?.status === 'failed'

  return (
    <div className={styles.pollingOverlay}>
      <div className={styles.pollingCard}>
        <div className={`${styles.pollingIcon} ${settled ? styles.pollingSuccess : failed ? styles.pollingFail : styles.pollingPending}`}>
          {settled ? '✓' : failed ? '✗' : '⏳'}
        </div>
        <h2 className={styles.pollingTitle}>
          {settled
            ? 'Payment Successful!'
            : failed
            ? 'Payment Failed'
            : 'Processing Payment…'}
        </h2>
        <p className={styles.pollingStatus}>
          {status ? statusLabel[status.status] ?? status.status : 'Waiting for confirmation…'}
        </p>
        {settled && creditsGranted > 0 && (
          <p className={styles.pollingCredits}>
            {creditsGranted} credits have been added to your wallet.
          </p>
        )}
        {failed && (
          <p className={styles.pollingError}>
            Your payment could not be processed. No charges were made.
            If you were charged, please contact support.
          </p>
        )}
        {(settled || failed) && (
          <button className={styles.pollingDoneBtn} onClick={onDone}>
            {settled ? 'Go to Wallet' : 'Try Again'}
          </button>
        )}
        {!settled && !failed && (
          <div className={styles.pollingSpinner} />
        )}
      </div>
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function PurchasePage() {
  const router = useRouter()
  const { user, isAuthenticated, sessionChecked, updateWalletBalance } = useAuthStore()
  const [plans, setPlans] = useState<CreditPlan[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCheckingOut, setIsCheckingOut] = useState(false)
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_currentOrder, setCurrentOrder] = useState<PaymentOrder | null>(null)
  const [pollingStatus, setPollingStatus] = useState<PaymentStatus | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const pollCountRef = useRef(0)
  const pollTimerRef = useRef<NodeJS.Timeout | null>(null)

  // ── Auth guard ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (sessionChecked && !isAuthenticated) {
      router.push('/?from=/purchase')
    }
  }, [sessionChecked, isAuthenticated, router])

  // ── Load plans ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAuthenticated) return
    getCreditPlans()
      .then(data => {
        const sorted = data.sort((a, b) => (a.amount_inr || 0) - (b.amount_inr || 0))
        setPlans(sorted)
      })
      .catch(() => setError('Failed to load plans. Please refresh.'))
      .finally(() => setIsLoading(false))
  }, [isAuthenticated])

  // ── Cleanup polling on unmount ─────────────────────────────────────────────
  useEffect(() => {
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [])

  // ── Poll payment status ────────────────────────────────────────────────────
  const startPolling = useCallback((razorpayOrderId: string) => {
    pollCountRef.current = 0
    setIsPolling(true)

    pollTimerRef.current = setInterval(async () => {
      pollCountRef.current += 1

      try {
        const status = await getPaymentStatus(razorpayOrderId)
        setPollingStatus(status)

        if (status.status === 'settled') {
          clearInterval(pollTimerRef.current!)
          setIsPolling(false)
          // Update wallet balance in Zustand store so Navbar reflects new balance
          if (status.credits_granted) {
            const currentBalance = user?.wallet?.balance_credits ?? 0
            updateWalletBalance(currentBalance + status.credits_granted)
          }
          return
        }

        if (status.status === 'failed') {
          clearInterval(pollTimerRef.current!)
          setIsPolling(false)
          return
        }

        // Timeout after max attempts
        if (pollCountRef.current >= POLL_MAX_ATTEMPTS) {
          clearInterval(pollTimerRef.current!)
          setIsPolling(false)
          setPollingStatus((prev: PaymentStatus | null) => prev ? { ...prev, status: 'failed' as const } : null)
        }
      } catch {
        // Network error during polling — keep trying
      }
    }, POLL_INTERVAL_MS)
  }, [user, updateWalletBalance])

  // ── Checkout flow ──────────────────────────────────────────────────────────
  const handleSelectPlan = async (plan: CreditPlan) => {
    setSelectedPlanId(plan.id)
    setIsCheckingOut(true)
    setError(null)

    try {
      // Load Razorpay SDK
      const sdkLoaded = await loadRazorpayScript()
      if (!sdkLoaded) {
        setError('Failed to load payment SDK. Please check your internet connection.')
        setIsCheckingOut(false)
        return
      }

      // Create Razorpay order on backend
      const order = await createPaymentOrder(plan.id)
      setCurrentOrder(order)

      // Open Razorpay modal
      const razorpay = new window.Razorpay({
        key: order.razorpay_key_id,
        order_id: order.razorpay_order_id,
        amount: order.amount_paise,
        currency: order.currency,
        name: 'VYAS',
        description: `${order.credits_to_grant} credits`,
        prefill: {
          name: user?.name,
          email: user?.email,
          contact: '', // empty string prevents Razorpay from prefilling its cached phone number
        },
        theme: { color: '#d4a843' }, // VYAS gold
        // On desktop: hide UPI intent tiles (Google Pay / PhonePe deep links)
        // because they require a UPI app installed locally and hang indefinitely.
        // QR code + "Enter UPI ID" options remain visible.
        // On mobile: show full default UI — intent links open apps correctly.
        ...(!isMobileDevice() && {
          config: {
            display: {
              hide: [{ method: 'upi', flows: ['intent'] }],
              preferences: { show_default_blocks: true },
            },
          },
        }),
        modal: {
          ondismiss: () => {
            // User closed modal without paying
            setIsCheckingOut(false)
            setSelectedPlanId(null)
          },
        },
        handler: async (response: RazorpaySuccessResponse) => {
          // Payment completed client-side — verify on backend and start polling
          setIsCheckingOut(false)

          try {
            // BUG FIX: verifyPayment takes a single object argument, not 3 positional args
            await verifyPayment({
              razorpay_order_id:  response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            })
          } catch {
            // Verify call can fail — credits are still granted via webhook.
            // We continue polling to show the user the outcome.
          }

          // Start polling for webhook settlement
          // BUG FIX: 'initiated' is not a valid PaymentStatus.status — use 'created'
          // (the earliest valid backend status; 'initiated' was a UI-only sentinel)
          setPollingStatus({
            internal_order_id: order.internal_order_id,
            razorpay_order_id: order.razorpay_order_id,
            status: 'created',
            credits_granted: null,
            amount_inr: plan.amount_inr,
            failure_reason: null,
          })
          startPolling(order.razorpay_order_id)
        },
      })

      razorpay.open()

    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to initiate checkout'
      setError(msg)
      setIsCheckingOut(false)
      setSelectedPlanId(null)
    }
  }

  // ── Polling done handler ───────────────────────────────────────────────────
  const handlePollingDone = () => {
    if (pollingStatus?.status === 'settled') {
      router.push('/wallet')
    } else {
      // Reset for retry
      setPollingStatus(null)
      setCurrentOrder(null)
      setSelectedPlanId(null)
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  if (!sessionChecked || (sessionChecked && !isAuthenticated)) {
    return null
  }

  return (
    <div className={styles.page}>
      <Navbar />
      <main className={styles.main}>
        <div className={styles.header}>
          <h1 className={styles.title}>Buy Credits</h1>
          <p className={styles.subtitle}>
            Power your exam prep with AI-generated mock tests and VYAS Explain.
          </p>
          {user?.wallet && (
            <p className={styles.currentBalance}>
              Current balance:{' '}
              <strong>{user.wallet.balance_credits.toFixed(2)} credits</strong>
            </p>
          )}
        </div>

        {/* How credits work */}
        <div className={styles.infoStrip}>
          <div className={styles.infoItem}>
            <span className={styles.infoIcon}>🎯</span>
            <span>1 credit = ~6 AI questions generated</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoIcon}>💡</span>
            <span>0.5 credits per VYAS Explain</span>
          </div>
          <div className={styles.infoItem}>
            <span className={styles.infoIcon}>🎁</span>
            <span>Credits never expire</span>
          </div>
        </div>

        {error && (
          <div className={styles.errorBanner}>
            <p>{error}</p>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {isLoading ? (
          <div className={styles.loadingState}>
            <div className={styles.spinner} />
            <p>Loading plans…</p>
          </div>
        ) : (
          <div className={styles.plansGrid}>
            {plans.map(plan => (
              <PlanCard
                key={plan.id}
                plan={plan}
                isSelected={selectedPlanId === plan.id}
                isLoading={isCheckingOut && selectedPlanId === plan.id}
                onSelect={handleSelectPlan}
              />
            ))}
          </div>
        )}

        <div className={styles.securityNote}>
          <span className={styles.securityIcon}>🔒</span>
          <p>
            Payments are processed securely by{' '}
            <strong>Razorpay</strong>. We never store your card details.
            Credits are added instantly after payment confirmation.
          </p>
        </div>
      </main>

      {/* Polling overlay — shown after payment modal closes */}
      {(isPolling || pollingStatus?.status === 'settled' || pollingStatus?.status === 'failed') && (
        <PollingStatus
          status={pollingStatus}
          creditsGranted={pollingStatus?.credits_granted ?? 0}
          onDone={handlePollingDone}
        />
      )}
    </div>
  )
}