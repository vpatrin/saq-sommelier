import { useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'

const BASE_URL = '/api'

export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
    this.detail = detail
  }
}

export async function api<T>(
  path: string,
  options: RequestInit & { token?: string | null; onUnauthorized?: () => void } = {}
): Promise<T> {
  const { token, onUnauthorized, headers: extraHeaders, ...fetchOptions } = options

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((extraHeaders as Record<string, string>) ?? {}),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...fetchOptions,
    headers,
  })

  if (!response.ok) {
    if (response.status === 401 && onUnauthorized) {
      onUnauthorized()
    }
    const body = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(response.status, body.detail ?? response.statusText)
  }

  // 204 No Content has no body — return undefined instead of parsing
  if (response.status === 204) return undefined as T

  return response.json() as Promise<T>
}

// Returns an api() wrapper that auto-attaches the JWT from AuthContext.
// Use this in any authenticated component instead of passing token manually.
export function useApiClient() {
  const { token, logout } = useAuth()

  return useCallback(
    <T>(path: string, options: RequestInit = {}) =>
      api<T>(path, { ...options, token, onUnauthorized: logout }),
    [token, logout]
  )
}
