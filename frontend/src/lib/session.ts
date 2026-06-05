import type { User } from '@/types'
import type { ApiUser } from '@/lib/api'

export function readSession(): User | null {
  try {
    const raw = localStorage.getItem('mai_user')
    return raw ? (JSON.parse(raw) as User) : null
  } catch {
    return null
  }
}

export function writeSession(user: User | null): void {
  try {
    if (user) localStorage.setItem('mai_user', JSON.stringify(user))
    else localStorage.removeItem('mai_user')
  } catch {
    // ignore
  }
}

export function apiUserToLocal(apiUser: ApiUser): User {
  const nameFallback = apiUser.email.split('@')[0].replace(/[._-]+/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  return {
    name: apiUser.display_name || nameFallback,
    email: apiUser.email,
    department: 'Engineering',
    region: 'eu',
    signedInAt: Date.now(),
  }
}
