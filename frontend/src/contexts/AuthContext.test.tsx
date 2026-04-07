import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { AuthProvider, useAuth } from './AuthContext'

// AuthProvider fires /users/me on mount when a stored token exists
const fetchMock = vi.fn()
vi.stubGlobal('fetch', fetchMock)

function fakeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256' }))
  const body = btoa(JSON.stringify(payload))
  return `${header}.${body}.fakesig`
}

const TOKEN_KEY = 'auth_token'

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>
}

function stubHydration() {
  fetchMock.mockResolvedValue({
    ok: false,
    status: 401,
    statusText: 'Unauthorized',
    json: () => Promise.resolve({ detail: 'Unauthorized' }),
  } as Response)
}

beforeEach(() => {
  fetchMock.mockReset()
  localStorage.clear()
  stubHydration()
})

describe('useAuth', () => {
  it('throws when used outside AuthProvider', () => {
    expect(() => renderHook(() => useAuth())).toThrow('useAuth must be used within AuthProvider')
  })

  it('starts logged out when no stored token', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
  })
})

describe('login / logout', () => {
  it('login sets token and decodes user from JWT', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    const jwt = fakeJwt({ sub: '42', display_name: 'Victor', role: 'user' })

    act(() => result.current.login(jwt))

    expect(result.current.token).toBe(jwt)
    expect(result.current.user).toEqual({
      id: 42,
      display_name: 'Victor',
      locale: null,
      role: 'user',
    })
    expect(localStorage.getItem(TOKEN_KEY)).toBe(jwt)
  })

  it('logout clears token, user, and localStorage', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    const jwt = fakeJwt({ sub: '1', role: 'user' })

    act(() => result.current.login(jwt))
    act(() => result.current.logout())

    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})

describe('stored token', () => {
  it('restores session from localStorage on mount', () => {
    const jwt = fakeJwt({
      sub: '7',
      display_name: 'Stored',
      role: 'admin',
      exp: Date.now() / 1000 + 3600,
    })
    localStorage.setItem(TOKEN_KEY, jwt)

    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.token).toBe(jwt)
    expect(result.current.user?.id).toBe(7)
    expect(result.current.user?.role).toBe('admin')
  })

  it('clears expired token on mount', () => {
    const jwt = fakeJwt({ sub: '7', role: 'user', exp: Date.now() / 1000 - 3600 })
    localStorage.setItem(TOKEN_KEY, jwt)

    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.token).toBeNull()
    expect(result.current.user).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('clears malformed token on mount', () => {
    localStorage.setItem(TOKEN_KEY, 'not-a-jwt')

    const { result } = renderHook(() => useAuth(), { wrapper })
    expect(result.current.token).toBeNull()
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})

describe('hydration', () => {
  it('fetches /users/me and updates display_name and locale', async () => {
    const jwt = fakeJwt({
      sub: '5',
      display_name: 'Old',
      role: 'user',
      exp: Date.now() / 1000 + 3600,
    })
    localStorage.setItem(TOKEN_KEY, jwt)

    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({
          id: 5,
          email: 'v@test.com',
          display_name: 'Updated',
          locale: 'en',
          role: 'user',
        }),
    } as Response)

    const { result } = renderHook(() => useAuth(), { wrapper })

    await waitFor(() => {
      expect(result.current.user?.display_name).toBe('Updated')
    })
    expect(result.current.user?.locale).toBe('en')
  })
})

describe('updateUser', () => {
  it('patches user fields locally', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })
    const jwt = fakeJwt({ sub: '1', display_name: 'Before', role: 'user' })

    act(() => result.current.login(jwt))
    act(() => result.current.updateUser({ display_name: 'After' }))

    expect(result.current.user?.display_name).toBe('After')
  })

  it('leaves state unchanged when called while logged out', () => {
    const { result } = renderHook(() => useAuth(), { wrapper })

    act(() => result.current.updateUser({ display_name: 'Ghost' }))
    expect(result.current.user).toBeNull()
  })
})
