import { createContext, useContext, useState, useCallback } from 'react'
import type { ReactNode } from 'react'

interface User {
  id: number
  telegram_id: number
  first_name: string
  role: string
}

interface AuthContextValue {
  token: string | null
  user: User | null
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

function decodeUser(token: string): User {
  const payload = JSON.parse(atob(token.split('.')[1]))
  return {
    id: Number(payload.sub),
    telegram_id: payload.telegram_id,
    first_name: payload.first_name,
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
    return {
      token: stored,
      user: {
        id: Number(payload.sub),
        telegram_id: payload.telegram_id,
        first_name: payload.first_name,
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

  return (
    <AuthContext.Provider value={{ token, user, login, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
