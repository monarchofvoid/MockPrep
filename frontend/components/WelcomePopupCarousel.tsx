'use client'

/**
 * VYAS v2.0 — Welcome Popup Carousel
 * =====================================
 * v2.1.5 API migration:
 *   - Removed `api` namespace import (no longer exported by api.ts)
 *   - Replaced api.auth.ackPopup() → acknowledgePopup() named import
 *
 * All card logic, animation, sessionStorage guard, and popup sequencing
 * are fully preserved.
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { useAuthStore } from '@/stores/authStore'
import { acknowledgePopup } from '@/lib/api'
import VyasLogo from '@/components/VyasLogo'
import styles from '@/styles/WelcomePopup.module.css'

/* ─── Types ──────────────────────────────────────────────────────────────── */

type CardId = 'intro1' | 'intro2' | 'ai-mock-ad' | 'explain-ad' | 'premium'

/* ─── Deterministic random card selection ────────────────────────────────── */

const REGULAR_CARDS: Exclude<CardId, 'premium'>[] = [
  'intro1',
  'intro2',
  'ai-mock-ad',
  'explain-ad',
]

function pickRandomCard(): Exclude<CardId, 'premium'> {
  return REGULAR_CARDS[Math.floor(Math.random() * REGULAR_CARDS.length)]
}

/* ─── Shared card props ──────────────────────────────────────────────────── */

interface CardProps {
  onClose: () => void
  onNext?: () => void
}

/* ─── Card 1: Platform Intro ─────────────────────────────────────────────── */

function IntroCard1({ onClose, onNext }: CardProps) {
  const router = useRouter()
  return (
    <div className={`${styles.card} ${styles.introCard}`}>
      <div className={`${styles.introOrb} ${styles.orbA}`} />
      <div className={`${styles.introOrb} ${styles.orbB}`} />
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
      <div className={styles.introCardInner}>
        <div className={styles.introBrand}>
          <VyasLogo size={32} animate />
          <span className={styles.introBrandName}>VYAS</span>
        </div>
        <p className={styles.introTagline}>Your Intelligent Exam Partner</p>
        <h2 className={styles.introHeadline}>
          Crack competitive exams with <em>AI-powered</em> precision
        </h2>
        <p className={styles.introDesc}>
          VYAS gives you access to real past year question papers, AI-generated
          mocks tailored to your weak areas, and a deep analytics engine that
          tracks exactly where you need to improve.
        </p>
        <div className={styles.introPills}>
          <span className={styles.pill}>✦ CUET</span>
          <span className={styles.pill}>JEE</span>
          <span className={styles.pill}>NEET</span>
          <span className={styles.pill}>GATE</span>
          <span className={styles.pill}>+ more</span>
        </div>
        <div className={styles.introCta}>
          <button
            className={styles.ctaPrimary}
            onClick={() => { router.push('/mocks'); onClose() }}
          >
            Explore Papers →
          </button>
          {onNext ? (
            <button className={styles.ctaNext} onClick={onNext}>Next</button>
          ) : (
            <button className={styles.ctaNext} onClick={onClose}>Got it</button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Card 2: How VYAS Helps ─────────────────────────────────────────────── */

function IntroCard2({ onClose, onNext }: CardProps) {
  const router = useRouter()
  const features = [
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="3" y="2" width="14" height="16" rx="2" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M6 6h8M6 9h8M6 12h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      ),
      title: 'PYQ Papers',    desc: 'Full past year papers, year-wise and topic-filtered.',
    },
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M10 2L12.4 7.6L18 8.2L13.8 12.2L15 18L10 15.2L5 18L6.2 12.2L2 8.2L7.6 7.6L10 2Z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        </svg>
      ),
      title: 'AI Mock Gen',   desc: 'Personalised tests built around your weak spots.',
    },
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M3 14l4-5 3 3 3-4 4 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          <rect x="2" y="2" width="16" height="16" rx="2" stroke="currentColor" strokeWidth="1.5"/>
        </svg>
      ),
      title: 'ELO Analytics', desc: 'Adaptive ranking shows your real preparation level.',
    },
    {
      icon: (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="8" r="5" stroke="currentColor" strokeWidth="1.5"/>
          <path d="M10 6v2.5l1.5 1.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          <path d="M7 15c0-1.7 1.3-3 3-3s3 1.3 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
      ),
      title: 'VYAS Explain',  desc: 'Instant AI explanations for any question.',
    },
  ]
  return (
    <div className={`${styles.card} ${styles.introCard}`}>
      <div className={`${styles.introOrb} ${styles.orbA}`} />
      <div className={`${styles.introOrb} ${styles.orbB}`} />
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
      <div className={styles.introCardInner}>
        <div className={styles.introBrand}>
          <VyasLogo size={32} animate />
          <span className={styles.introBrandName}>VYAS</span>
        </div>
        <p className={styles.introTagline}>Everything you need in one platform</p>
        <h2 className={styles.introHeadline}>
          Your complete <em>preparation engine</em>
        </h2>
        <div className={styles.featureGrid}>
          {features.map((f) => (
            <div key={f.title} className={styles.featureTile}>
              <div className={styles.featureTileIcon}>{f.icon}</div>
              <div className={styles.featureTileTitle}>{f.title}</div>
              <div className={styles.featureTileDesc}>{f.desc}</div>
            </div>
          ))}
        </div>
        <div className={styles.introCta}>
          <button
            className={styles.ctaPrimary}
            onClick={() => { router.push('/mocks'); onClose() }}
          >
            Explore Papers →
          </button>
          {onNext ? (
            <button className={styles.ctaNext} onClick={onNext}>Next</button>
          ) : (
            <button className={styles.ctaNext} onClick={onClose}>Got it</button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Card 3: AI Mock Generator Ad ──────────────────────────────────────── */

function AIMockAdCard({ onClose, onNext }: CardProps) {
  const router = useRouter()
  return (
    <div className={`${styles.card} ${styles.aiMockCard}`}>
      <div className={`${styles.introOrb} ${styles.blueOrbA}`} />
      <div className={`${styles.introOrb} ${styles.blueOrbB}`} />
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
      <div className={styles.aiCardInner}>
        <div className={styles.aiCardBadge}>
          <span className={styles.aiCardBadgeDot} />
          New · AI Feature
        </div>
        <h2 className={styles.aiHeadline}>
          Generate a <em>personalised mock</em> in seconds
        </h2>
        <p className={styles.aiDesc}>
          VYAS Mock Generator builds a fresh question paper tuned to your
          exact proficiency gaps — so every test pushes you forward.
        </p>
        <div className={styles.aiTerminal}>
          <div className={styles.terminalHeader}>
            <span className={`${styles.termDot} ${styles.termRed}`} />
            <span className={`${styles.termDot} ${styles.termYellow}`} />
            <span className={`${styles.termDot} ${styles.termGreen}`} />
          </div>
          <div className={styles.terminalLine}><span>$</span><span>vyas generate --exam CUET --subject Economics</span></div>
          <div className={styles.terminalLine}><span>→</span><span>Analysing proficiency gaps…</span></div>
          <div className={styles.terminalLine}><span>→</span><span>Building 40 targeted questions</span></div>
          <div className={styles.terminalLine}><span>✓</span><span>Mock ready. ELO impact: +24 pts</span></div>
          <div className={styles.terminalLine}><span>&gt;</span><span><span className={styles.termCursor} /></span></div>
        </div>
        <div className={styles.aiCardCta}>
          <button
            className={styles.ctaBlue}
            onClick={() => { router.push('/ai-mock'); onClose() }}
          >
            Try Mock AI Gen →
          </button>
          {onNext ? (
            <button className={styles.ctaNext} onClick={onNext}>Next</button>
          ) : (
            <button className={styles.ctaNext} onClick={onClose}>Got it</button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Card 4: VYAS Explain Ad ────────────────────────────────────────────── */

function VyasExplainAdCard({ onClose, onNext }: CardProps) {
  const router = useRouter()
  return (
    <div className={`${styles.card} ${styles.explainCard}`}>
      <div className={`${styles.introOrb} ${styles.purpleOrbA}`} />
      <div className={`${styles.introOrb} ${styles.purpleOrbB}`} />
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
      <div className={styles.explainCardInner}>
        <div className={styles.explainBadge}>
          <span className={styles.explainBadgeDot} />
          AI Tutor · On-Demand
        </div>
        <h2 className={styles.explainHeadline}>
          Stuck on a question?<br /><em>VYAS Explains</em> instantly
        </h2>
        <p className={styles.explainDesc}>
          Every question in every paper comes with a deep, step-by-step
          AI explanation — concept links, common mistakes, and exam tips included.
        </p>
        <div className={styles.explainBubbleFlow}>
          <div className={styles.bubbleRow}>
            <div className={styles.bubbleQ}>Q</div>
            <div className={`${styles.bubbleText} ${styles.question}`}>
              Why does GDP deflator differ from CPI?
            </div>
          </div>
          <div className={styles.bubbleRow}>
            <div className={styles.bubbleA}>A</div>
            <div className={`${styles.bubbleText} ${styles.answer}`}>
              GDP deflator covers all domestic goods; CPI tracks a fixed
              basket of consumer goods. Key exam distinction: deflator has no
              fixed base basket.
            </div>
          </div>
        </div>
        <div className={styles.explainCardCta}>
          <button
            className={styles.ctaPurple}
            onClick={() => { router.push('/ai-mock'); onClose() }}
          >
            VYAS Explain →
          </button>
          {onNext ? (
            <button className={styles.ctaNext} onClick={onNext}>Next</button>
          ) : (
            <button className={styles.ctaNext} onClick={onClose}>Got it</button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Card 5: Premium Credits Award (new users only) ─────────────────────── */

function PremiumRewardCard({ onClose, onNext }: CardProps) {
  const router = useRouter()
  return (
    <div className={`${styles.card} ${styles.premiumCard}`}>
      <div className={styles.premiumParticles}>
        {Array.from({ length: 12 }).map((_, i) => (
          <span key={i} className={styles.particle} />
        ))}
      </div>
      <div className={`${styles.introOrb} ${styles.goldOrbA}`} />
      <div className={`${styles.introOrb} ${styles.goldOrbB}`} />
      <button className={styles.closeBtn} onClick={onClose} aria-label="Close">✕</button>
      <div className={styles.premiumCardInner}>
        <div className={styles.awardMedallion}>
          <svg className={styles.awardSvg} width="38" height="38" viewBox="0 0 38 38" fill="none">
            <rect x="5" y="17" width="28" height="18" rx="2.5" stroke="currentColor" strokeWidth="1.8"/>
            <rect x="3" y="11" width="32" height="6" rx="2" stroke="currentColor" strokeWidth="1.8"/>
            <line x1="19" y1="11" x2="19" y2="35" stroke="currentColor" strokeWidth="1.8"/>
            <line x1="3" y1="14" x2="35" y2="14" stroke="currentColor" strokeWidth="1.8"/>
            <path d="M19 11 C16 8 10 6 11 3 C12 1 16 2 19 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            <path d="M19 11 C22 8 28 6 27 3 C26 1 22 2 19 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
        </div>
        <p className={styles.premiumTagline}>Welcome gift · One time only</p>
        <h2 className={styles.premiumHeadline}>
          You&apos;ve earned <em>5 free credits</em>
        </h2>
        <p className={styles.premiumSub}>
          We&apos;ve dropped 5 credits into your VYAS wallet — use them to generate
          AI mocks, unlock explanations, and power up your prep.
        </p>
        <div className={styles.creditsDisplay}>
          <span className={styles.creditsNumber}>5</span>
          <div className={styles.creditsLabel}>
            <span className={styles.creditsLabelTitle}>Free Credits</span>
            <span className={styles.creditsLabelSub}>Added to your wallet</span>
          </div>
        </div>
        <div className={styles.premiumCta}>
          <button
            className={styles.ctaGold}
            onClick={() => { router.push('/wallet'); onClose() }}
          >
            Checkout Wallet →
          </button>
          {onNext ? (
            <button className={styles.ctaMuted} onClick={onNext}>See what&apos;s inside →</button>
          ) : (
            <button className={styles.ctaMuted} onClick={onClose}>Maybe later</button>
          )}
        </div>
      </div>
    </div>
  )
}

/* ─── Main Carousel ──────────────────────────────────────────────────────── */

export default function WelcomePopupCarousel() {
  const { user, isAuthenticated, markPremiumPopupSeen } = useAuthStore()

  const [visible,   setVisible]   = useState(false)
  const [exiting,   setExiting]   = useState(false)
  const [shaking,   setShaking]   = useState(false)
  const [cardOut,   setCardOut]   = useState(false)
  const [cardIndex, setCardIndex] = useState(0)

  const cardsRef = useRef<CardId[] | null>(null)
  if (cardsRef.current === null) {
    const isNewUser    = user && !user.has_seen_premium_popup
    const randomRegular = pickRandomCard()
    cardsRef.current = isNewUser
      ? ['premium', randomRegular]
      : [randomRegular]
  }
  const cards = cardsRef.current

  const hasAckedRef = useRef(false)

  const SESSION_KEY = 'vyas_popup_shown'

  useEffect(() => {
    if (!isAuthenticated) return
    if (sessionStorage.getItem(SESSION_KEY)) return
    const t = setTimeout(() => {
      sessionStorage.setItem(SESSION_KEY, '1')
      setVisible(true)
    }, 600)
    return () => clearTimeout(t)
  }, [isAuthenticated])

  // FIX: was api.auth.ackPopup() → acknowledgePopup() named import
  const ackPopup = useCallback(async () => {
    if (hasAckedRef.current) return
    hasAckedRef.current = true
    if (cards.includes('premium')) {
      try {
        await acknowledgePopup()
        markPremiumPopupSeen()
      } catch {
        // Non-critical — ignore
      }
    }
  }, [cards, markPremiumPopupSeen])

  const closePopup = useCallback(() => {
    setExiting(true)
    ackPopup()
    setTimeout(() => setVisible(false), 350)
  }, [ackPopup])

  const handleXClose = useCallback(() => {
    if (shaking) return
    setShaking(true)
    setTimeout(() => {
      setShaking(false)
      closePopup()
    }, 420)
  }, [shaking, closePopup])

  const handleNext = useCallback(() => {
    if (cardIndex >= cards.length - 1) {
      closePopup()
      return
    }
    setCardOut(true)
    setTimeout(() => {
      setCardOut(false)
      setCardIndex((i) => i + 1)
    }, 360)
  }, [cardIndex, cards.length, closePopup])

  if (!visible) return null

  const currentCard = cards[cardIndex]
  const isLast      = cardIndex === cards.length - 1

  const cardProps: CardProps = {
    onClose: handleXClose,
    onNext:  isLast ? undefined : handleNext,
  }

  const cardExtraClass = shaking ? styles.shaking : cardOut ? styles.cardOut : ''

  return (
    <div
      className={`${styles.overlay} ${exiting ? styles.exiting : ''}`}
      role="dialog"
      aria-modal="true"
      aria-label="Welcome to VYAS"
    >
      <div className={styles.slideTrack}>
        <div key={currentCard} className={cardExtraClass}>
          {currentCard === 'intro1'      && <IntroCard1         {...cardProps} />}
          {currentCard === 'intro2'      && <IntroCard2         {...cardProps} />}
          {currentCard === 'ai-mock-ad'  && <AIMockAdCard       {...cardProps} />}
          {currentCard === 'explain-ad'  && <VyasExplainAdCard  {...cardProps} />}
          {currentCard === 'premium'     && <PremiumRewardCard  {...cardProps} />}
        </div>

        {cards.length > 1 && (
          <div className={styles.dotsRow}>
            {cards.map((id, i) => (
              <span
                key={id}
                className={`${styles.dot} ${
                  i === cardIndex ? styles.active : i < cardIndex ? styles.done : ''
                }`}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}