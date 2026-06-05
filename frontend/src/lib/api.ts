const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000/api/v1'

// ─── Token storage ────────────────────────────────────────────────────────

export function getToken(): string | null {
  try { return localStorage.getItem('mai_token') } catch { return null }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem('mai_token', token)
    else localStorage.removeItem('mai_token')
  } catch { /* ignore */ }
}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(init.headers ?? {}) },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.title ?? `HTTP ${res.status}`)
  }
  return res
}

// ─── Auth ─────────────────────────────────────────────────────────────────

export interface ApiUser {
  id: string
  email: string
  display_name: string | null
  created_at: string
  last_login_at: string | null
}

export async function devLogin(): Promise<{ access_token: string; user: ApiUser }> {
  const res = await fetch(`${API_BASE}/auth/dev-login`, { method: 'POST' })
  if (!res.ok) throw new Error(`dev-login failed: ${res.status}`)
  return res.json()
}

export async function getMe(): Promise<ApiUser> {
  const res = await apiFetch('/me')
  return res.json()
}

export async function logout(): Promise<void> {
  await apiFetch('/auth/logout', { method: 'POST' }).catch(() => {/* stateless, best-effort */})
  setToken(null)
}

// ─── Sessions ─────────────────────────────────────────────────────────────

export interface ApiSession {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export async function createSession(title?: string): Promise<ApiSession> {
  const res = await apiFetch('/me/sessions', {
    method: 'POST',
    body: JSON.stringify({ title: title ?? null }),
  })
  return res.json()
}

export async function listSessions(limit = 30): Promise<ApiSession[]> {
  const res = await apiFetch(`/me/sessions?limit=${limit}`)
  const page = await res.json()
  return page.data ?? []
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiFetch(`/me/sessions/${sessionId}`, { method: 'DELETE' })
}

// ─── SSE streaming ────────────────────────────────────────────────────────

export interface SseCitation {
  index: number
  article_id: string
  title: string
  source: string
  url: string
  published_at: string
}

export async function streamMessage(
  sessionId: string,
  content: string,
  callbacks: {
    onToken: (text: string) => void
    onCitation: (c: SseCitation) => void
    onDone: (messageId: string) => void
    onError: (err: Error) => void
  },
): Promise<void> {
  const token = getToken()
  const res = await fetch(`${API_BASE}/me/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
  })

  if (!res.ok || !res.body) {
    const body = await res.json().catch(() => ({}))
    callbacks.onError(new Error(body?.title ?? `HTTP ${res.status}`))
    return
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let messageId = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const frames = buffer.split('\n\n')
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      if (!frame.trim()) continue
      const lines = frame.split('\n')
      let eventType = ''
      let dataStr = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) eventType = line.slice(7).trim()
        if (line.startsWith('data: ')) dataStr = line.slice(6).trim()
      }
      if (!dataStr) continue
      try {
        const data = JSON.parse(dataStr)
        if (eventType === 'turn_start') messageId = data.message_id
        if (eventType === 'token') callbacks.onToken(data.content)
        if (eventType === 'citation') callbacks.onCitation(data as SseCitation)
        if (eventType === 'turn_end') callbacks.onDone(messageId)
      } catch { /* malformed frame, skip */ }
    }
  }
}

// ─── Preferences ──────────────────────────────────────────────────────────

export interface ApiPreferences {
  topics: string[]
  business_tags: string[]
  regulation_tags: string[]
  regions: string[]
  role: string | null
  muted_sources: string[]
  frequency: 'daily' | 'weekdays' | 'weekly'
  delivery_day: string
  delivery_hour_local: number
  length: 'short' | 'standard' | 'deep'
  tone: 'technical' | 'business' | 'executive'
  language: string
  timezone?: string
}

export async function getPreferences(): Promise<ApiPreferences> {
  const res = await apiFetch('/me/preferences')
  return res.json()
}

export async function putPreferences(prefs: Partial<ApiPreferences>): Promise<ApiPreferences> {
  const res = await apiFetch('/me/preferences', {
    method: 'PUT',
    body: JSON.stringify(prefs),
  })
  return res.json()
}

// ─── Tags (for preferences UI) ────────────────────────────────────────────

export interface ApiTag { slug: string; label: string }

export async function getTags(): Promise<Record<string, ApiTag[]>> {
  const res = await apiFetch('/tags')
  return res.json()
}
