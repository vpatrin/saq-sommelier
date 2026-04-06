import { createContext, useContext, useState, useCallback, useEffect } from 'react'
import type { ReactNode } from 'react'
import type { UserRole } from '@/lib/types'
import { api } from '@/lib/api'
import i18n from '@/i18n'

interface User {
  id: number
  display_name: string | null
  locale: string | null
  role: UserRole
}

interface ProfileResponse {
  id: number
  email: string
  display_name: string | null
  locale: string | null
  role: UserRole
}

interface AuthContextValue {
  token: string | null
  user: User | null
  login: (token: string) => void
  logout: () => void
  updateUser: (updates: Partial<Pick<User, 'display_name' | 'locale'>>) => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function decodeUser(token: string): User {
  const payload = JSON.parse(atob(token.split('.')[1]))
  return {
    id: Number(payload.sub),
    display_name: payload.display_name ?? null,
    locale: null,
    role: payload.role,
  }
}

const TOKEN_KEY = 'auth_token'

function loadStoredToken(): { token: string; user: User } | null {
  const stored = localStorage.getItem(TOKEN_KEY)
  if (!stored) return null
  try {
    const payload = JSON.parse(atob(stored.split('.')[1]))
    if (payload.exp && payload.exp < Date.now() / 1000) {
      localStorage.removeItem(TOKEN_KEY)
      return null
    }
    // Existing sessions predate onboarding — mark as completed
    if (!localStorage.getItem('onboarded')) localStorage.setItem('onboarded', '1')
    return {
      token: stored,
      user: {
        id: Number(payload.sub),
        display_name: payload.display_name ?? null,
        locale: null,
        role: payload.role,
      },
    }
  } catch {
    localStorage.removeItem(TOKEN_KEY)
    return null
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [stored] = useState(loadStoredToken)
  const [token, setToken] = useState<string | null>(stored?.token ?? null)
  const [user, setUser] = useState<User | null>(stored?.user ?? null)

  // Hydrate profile from server — syncs locale + display_name
  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    api<ProfileResponse>('/users/me', { token, signal: controller.signal })
      .then((profile) => {
        setUser((prev) =>
          prev ? { ...prev, display_name: profile.display_name, locale: profile.locale } : prev,
        )
        if (profile.locale) {
          i18n.changeLanguage(profile.locale)
        }
      })
      .catch(() => {})
    return () => controller.abort()
  }, [token])

  const login = useCallback((newToken: string) => {
    localStorage.setItem(TOKEN_KEY, newToken)
    setToken(newToken)
    setUser(decodeUser(newToken))
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  const updateUser = useCallback((updates: Partial<Pick<User, 'display_name' | 'locale'>>) => {
    setUser((prev) => (prev ? { ...prev, ...updates } : prev))
    // Sync locale to i18n when updated locally
    if (updates.locale) {
      i18n.changeLanguage(updates.locale)
    }
  }, [])

  return (
    <AuthContext.Provider value={{ token, user, login, logout, updateUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
