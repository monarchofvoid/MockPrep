'use client'

export default function GlobalError({
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          padding: '2rem',
        }}>
          <h2>Critical Error</h2>
          <p>The application encountered a critical error.</p>
          <button onClick={reset}>Try again</button>
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a href="/">Return to home</a>
        </div>
      </body>
    </html>
  )
}