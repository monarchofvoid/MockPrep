'use client'

/**
 * VYAS v2.0 — Route-level loading fallback
 * Used by Next.js for page transitions (not first-load intro).
 * The cinematic first-load experience lives in VyasIntro.tsx.
 */
export default function Loading() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: '#0a0a0a',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      {/* VYAS gold ring spinner */}
      <svg
        width="44"
        height="44"
        viewBox="0 0 44 44"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Loading"
      >
        <circle
          cx="22"
          cy="22"
          r="18"
          stroke="rgba(212,168,67,0.12)"
          strokeWidth="3"
        />
        <circle
          cx="22"
          cy="22"
          r="18"
          stroke="url(#vyasSpinGold)"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray="60 54"
          style={{ animation: 'vyasSpin 0.9s cubic-bezier(0.45,0,0.55,1) infinite' }}
        />
        <defs>
          <linearGradient id="vyasSpinGold" x1="0" y1="0" x2="44" y2="44" gradientUnits="userSpaceOnUse">
            <stop offset="0%"   stopColor="#f0c060" />
            <stop offset="100%" stopColor="#8a6020" />
          </linearGradient>
        </defs>
      </svg>

      <span
        style={{
          fontFamily: '"Cinzel", serif',
          fontSize: '11px',
          letterSpacing: '0.3em',
          color: 'rgba(212,168,67,0.45)',
          textTransform: 'uppercase',
        }}
      >
        VYAS
      </span>

      <style>{`
        @keyframes vyasSpin {
          from { transform: rotate(0deg); transform-origin: 22px 22px; }
          to   { transform: rotate(360deg); transform-origin: 22px 22px; }
        }
      `}</style>
    </div>
  )
}
