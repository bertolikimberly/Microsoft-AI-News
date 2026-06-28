'use client'

import { useState } from 'react'
import Backdrop from '@/components/ui/Backdrop'
import MaiMark from '@/components/ui/MaiMark'
import Wordmark from '@/components/ui/Wordmark'
import { FONTS, NEWS_FONTS } from '@/constants/fonts'
import { writeSession, apiUserToLocal } from '@/lib/session'
import { requestMagicLink, setToken, getMe, devLogin as apiDevLogin } from '@/lib/api'
import type { Palette, User } from '@/types'

interface Props {
  palette: Palette
  displayFont: string
  newsFont: string
  blur: number
  grain: number
  mode: 'signin' | 'signup'
  setMode: (m: 'signin' | 'signup') => void
  onAuthed: (user: User) => void
}

type UIState = 'idle' | 'loading' | 'sent'

export default function AuthGate({ palette, displayFont, newsFont, blur, grain, onAuthed }: Props) {
  const [email, setEmail] = useState('')
  const [uiState, setUiState] = useState<UIState>('idle')
  const [devLink, setDevLink] = useState<string | null>(null)
  const [error, setError] = useState('')

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = email.trim().toLowerCase()
    if (!trimmed || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      return setError('Enter a valid email address.')
    }
    setError('')
    setUiState('loading')
    try {
      const result = await requestMagicLink(trimmed)
      setDevLink(result.dev_link ?? null)
      setUiState('sent')
    } catch {
      setError('Could not send login link. Is the server running?')
      setUiState('idle')
    }
  }

  const handleDevLink = async () => {
    if (!devLink) return
    // Extract token from the dev link and verify it client-side via the backend
    window.location.href = devLink
  }

  const handleDevLogin = async () => {
    setUiState('loading')
    try {
      const data = await apiDevLogin()
      setToken(data.access_token)
      const apiUser = await getMe()
      const u = apiUserToLocal(apiUser)
      writeSession(u)
      onAuthed(u)
    } catch {
      setError('Dev login failed — is the server running?')
      setUiState('idle')
    }
  }

  const reset = () => {
    setUiState('idle')
    setDevLink(null)
    setError('')
    setEmail('')
  }

  return (
    <div className="auth-shell" style={{ color: palette.ink, fontFamily: "'Inter Tight', system-ui, sans-serif" }}>
      <Backdrop palette={palette} blur={blur} grain={grain} />

      <div className="auth-grid">
        <div className="auth-hero">
          <div className="brand auth-brand">
            <MaiMark palette={palette} size={44} />
            <Wordmark palette={palette} displayFont={displayFont} newsFont={newsFont} size={38} />
          </div>
          <h1 className="auth-headline" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
            Tech news,<br /><em>made yours.</em>
          </h1>
          <div className="auth-bullets" style={{ color: palette.muted }}>
            <p className="auth-line">Tech moves too fast. MAI personalizes the news to your role and region.</p>
            <p className="auth-line">Want to go deeper on any story? Chat with me — I'll pull sources.</p>
          </div>
        </div>

        <div className="auth-card-col">
          <div className="auth-card" style={{ background: palette.cardBg, borderColor: 'rgba(0,0,0,0.08)' }}>

            {uiState === 'sent' ? (
              <>
                <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
                  Check your inbox.
                </h2>
                <p className="auth-sub" style={{ color: palette.muted }}>
                  We sent a login link to <strong>{email}</strong>.<br />
                  Click it to sign in — the link expires in 15 minutes.
                </p>

                {devLink && (
                  <div style={{ marginTop: '1.5rem' }}>
                    <p style={{ color: palette.muted, fontSize: '0.78rem', marginBottom: '0.75rem' }}>
                      Dev mode — no email needed, click directly:
                    </p>
                    <button
                      type="button"
                      className="auth-submit"
                      onClick={handleDevLink}
                      style={{ background: palette.accent, color: '#fff', width: '100%' }}
                    >
                      Open login link →
                    </button>
                  </div>
                )}

                <button
                  type="button"
                  className="auth-link"
                  onClick={reset}
                  style={{ color: palette.muted, marginTop: '1.25rem', display: 'block' }}
                >
                  ← Use a different email
                </button>
              </>
            ) : (
              <>
                <h2 className="auth-h" style={{ fontFamily: FONTS[displayFont], color: palette.ink }}>
                  Sign in with email.
                </h2>
                <p className="auth-sub" style={{ color: palette.muted }}>
                  Enter your address and we&apos;ll send you a one-click login link. No password.
                </p>

                <form onSubmit={submit} className="auth-form" noValidate>
                  <label className="auth-field">
                    <span style={{ color: palette.muted }}>Email address</span>
                    <input
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="you@example.com"
                      autoComplete="email"
                      autoFocus
                      style={{ color: palette.ink, borderColor: 'rgba(0,0,0,0.16)' }}
                    />
                  </label>

                  {error && (
                    <div className="auth-error" style={{ color: palette.ink }}>{error}</div>
                  )}

                  <button
                    type="submit"
                    className="auth-submit"
                    disabled={uiState === 'loading'}
                    style={{ background: palette.ink, color: palette.bg }}
                  >
                    {uiState === 'loading' ? 'Sending…' : 'Send login link →'}
                  </button>
                </form>

                <div style={{ marginTop: '1.5rem', paddingTop: '1.25rem', borderTop: '1px solid rgba(0,0,0,0.07)' }}>
                  <p style={{ color: palette.muted, fontSize: '0.75rem', marginBottom: '0.75rem', textAlign: 'center' }}>
                    Local dev
                  </p>
                  <button
                    type="button"
                    onClick={handleDevLogin}
                    disabled={uiState === 'loading'}
                    style={{
                      width: '100%', padding: '0.6rem 1rem', borderRadius: '6px',
                      border: '1px solid rgba(0,0,0,0.15)', background: 'transparent',
                      color: palette.muted, fontSize: '0.82rem', cursor: 'pointer',
                    }}
                  >
                    Skip → enter as dev user
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
