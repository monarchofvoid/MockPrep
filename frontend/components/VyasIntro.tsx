/**
 * VYAS v2.0 — Cinematic Intro / Loading Screen  (v2.1.2)
 * ────────────────────────────────────────────────────────
 * Sits at z-index 9999 on top of the already-visible landing page.
 * No opacity gating on the page below — the intro simply overlays it,
 * plays the animation, then removes itself from the DOM.
 *
 * onComplete prop removed entirely. The overlay at z-index 9999 IS the
 * curtain; the page beneath is always at full opacity and fully interactive
 * once the overlay fades away.
 *
 * Timeline (≈ 2.8 s):
 *   0 ms    — paths start drawing (stroke-dashoffset)
 *   1350 ms — bloom: glow corona expands
 *   1750 ms — shrink: logo scales down
 *   2250 ms — fade: curtain opacity → 0
 *   2750 ms — component unmounts
 */

'use client'

import { useEffect, useState, useId } from 'react'

const PATHS = [
  { key: 'outer-left',  d: 'M21.61 46.01L109.61 198.01L130.39 185.99L42.39 33.99Z',  delay: 0 },
  { key: 'outer-right', d: 'M197.61 33.99L109.61 185.99L130.39 198.01L218.39 46.01Z', delay: 140 },
  { key: 'inner-left',  d: 'M80.73 76.21L112.73 131.48L127.27 123.06L95.27 67.79Z',  delay: 420 },
  { key: 'inner-right', d: 'M144.73 67.79L112.73 123.06L127.27 131.48L159.27 76.21Z', delay: 560 },
  { key: 'crown',       d: 'M120 16L152 64L136 64L120 40L104 64L88 64Z',              delay: 800 },
  { key: 'diamond',     d: 'M120 98.8L133.2 112L120 125.2L106.8 112Z',               delay: 1060 },
]

export default function VyasIntro() {
  const rawId     = useId().replace(/:/g, '')
  const goldId    = `ig-${rawId}`
  const glowId    = `gw-${rawId}`
  const glowBigId = `gwb-${rawId}`

  const [phase,   setPhase]   = useState<'draw' | 'bloom' | 'shrink' | 'fade'>('draw')
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    const t1 = setTimeout(() => setPhase('bloom'),  1350)
    const t2 = setTimeout(() => setPhase('shrink'), 1750)
    const t3 = setTimeout(() => setPhase('fade'),   2250)
    const t4 = setTimeout(() => setVisible(false),  2750)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4) }
  }, [])

  if (!visible) return null

  const isBloom  = phase === 'bloom'  || phase === 'shrink' || phase === 'fade'
  const isShrink = phase === 'shrink' || phase === 'fade'
  const isFade   = phase === 'fade'

  return (
    <div
      aria-hidden="true"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#0a0a0a',
        opacity: isFade ? 0 : 1,
        transition: isFade ? 'opacity 480ms cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
        /* Once fading, allow clicks to pass through to the page beneath */
        pointerEvents: isFade ? 'none' : 'all',
      }}
    >
      {/* Ambient radial glow */}
      <div
        style={{
          position: 'absolute',
          width: 480,
          height: 480,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(212,168,67,0.14) 0%, transparent 65%)',
          opacity: isBloom ? 1 : 0,
          transform: isBloom ? 'scale(1)' : 'scale(0.4)',
          transition: 'opacity 600ms cubic-bezier(0.34,1.56,0.64,1), transform 600ms cubic-bezier(0.34,1.56,0.64,1)',
          pointerEvents: 'none',
        }}
      />

      {/* Logo */}
      <div
        style={{
          position: 'relative',
          transform: isShrink ? 'scale(0.32) translateY(-4px)' : 'scale(1)',
          transition: isShrink ? 'transform 520ms cubic-bezier(0.4, 0, 0.2, 1)' : 'none',
          filter: isBloom && !isShrink
            ? 'drop-shadow(0 0 32px rgba(212,168,67,0.55)) drop-shadow(0 0 80px rgba(212,168,67,0.2))'
            : isShrink
            ? 'drop-shadow(0 0 8px rgba(212,168,67,0.3))'
            : 'none',
        }}
      >
        <svg
          width={160}
          height={150}
          viewBox="0 0 240 224"
          xmlns="http://www.w3.org/2000/svg"
          overflow="visible"
        >
          <defs>
            <linearGradient id={goldId} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%"   stopColor="#f0c060" />
              <stop offset="40%"  stopColor="#d4a843" />
              <stop offset="100%" stopColor="#8a6020" />
            </linearGradient>
            <filter id={glowId} x="-30%" y="-30%" width="160%" height="160%">
              <feDropShadow dx="0" dy="0" stdDeviation="4"  floodColor="#d4a843" floodOpacity="0.5" />
              <feDropShadow dx="0" dy="8" stdDeviation="16" floodColor="#8a6020" floodOpacity="0.25" />
            </filter>
            <filter id={glowBigId} x="-50%" y="-50%" width="200%" height="200%">
              <feDropShadow dx="0" dy="0" stdDeviation="10" floodColor="#f0c060" floodOpacity="0.6" />
              <feDropShadow dx="0" dy="0" stdDeviation="30" floodColor="#d4a843" floodOpacity="0.3" />
            </filter>
          </defs>

          <g filter={`url(#${isBloom && !isShrink ? glowBigId : glowId})`}>
            {PATHS.map((p) => {
              if (p.key === 'diamond') {
                return (
                  <path
                    key={p.key}
                    d={p.d}
                    fill={`url(#${goldId})`}
                    stroke={`url(#${goldId})`}
                    strokeWidth="1.5"
                    strokeLinejoin="round"
                    style={{
                      opacity: 0,
                      transform: 'scale(0.6)',
                      transformBox: 'fill-box',
                      transformOrigin: 'center',
                      animation: `vyasDiamond 320ms cubic-bezier(0.34,1.56,0.64,1) ${p.delay}ms forwards`,
                    }}
                  />
                )
              }
              return (
                <path
                  key={p.key}
                  d={p.d}
                  fill={`url(#${goldId})`}
                  stroke={`url(#${goldId})`}
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                  strokeDasharray={500}
                  strokeDashoffset={500}
                  style={{
                    animation: `vyasDraw 460ms cubic-bezier(0.25,0.46,0.45,0.94) ${p.delay}ms forwards`,
                  }}
                />
              )
            })}
          </g>
        </svg>
      </div>

      {/* Tagline */}
      <div
        style={{
          position: 'absolute',
          bottom: 'calc(50% - 120px)',
          left: '50%',
          transform: 'translateX(-50%)',
          fontFamily: 'var(--font-display, "Cinzel", serif)',
          fontSize: 13,
          fontWeight: 800,
          letterSpacing: '0.4em',
          color: 'rgba(212,168,67,0.65)',
          opacity: isBloom && !isShrink ? 1 : 0,
          transition: 'opacity 400ms cubic-bezier(0.4, 0, 0.2, 1) 200ms',
          whiteSpace: 'nowrap',
          userSelect: 'none',
        }}
      >
        INTELLIGENCE · DISCIPLINE · ASCENT
      </div>

      <style>{`
        @keyframes vyasDraw {
          from { stroke-dashoffset: 500; }
          to   { stroke-dashoffset: 0;   }
        }
        @keyframes vyasDiamond {
          from { opacity: 0; transform: scale(0.5); }
          to   { opacity: 1; transform: scale(1);   }
        }
      `}</style>
    </div>
  )
}