import { useState, useCallback } from 'react'
import { useNavigate, Navigate } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import {
  TelegramLoginButton,
  type TelegramLoginData,
} from '@/components/TelegramLoginButton'
import { api, ApiError } from '@/lib/api'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

interface TokenResponse {
  access_token: string
  token_type: string
}

function LoginPage() {
  const { token, login } = useAuth()
  const navigate = useNavigate()
  const [inviteCode, setInviteCode] = useState('')
  const [error, setError] = useState<string | null>(null)

  const handleAuth = useCallback(
    async (telegramData: TelegramLoginData) => {
      setError(null)
      try {
        const body = {
          ...telegramData,
          ...(inviteCode ? { invite_code: inviteCode } : {}),
        }
        const { access_token } = await api<TokenResponse>('/auth/telegram', {
          method: 'POST',
          body: JSON.stringify(body),
        })
        login(access_token)
        navigate('/dashboard', { replace: true })
      } catch (err) {
        if (err instanceof ApiError) {
          setError(err.detail)
        } else {
          setError('Authentication failed')
        }
      }
    },
    [inviteCode, login, navigate]
  )

  if (token) return <Navigate to="/dashboard" replace />

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-6">
      <h1 className="text-4xl font-mono font-bold">Coupette</h1>
      <p className="text-muted-foreground">
        Wine discovery & recommendations
      </p>

      <div className="flex flex-col items-center gap-4 w-72">
        <input
          type="text"
          placeholder="Invite code (new users only)"
          value={inviteCode}
          onChange={(e) => setInviteCode(e.target.value)}
          className="w-full px-4 py-2 bg-muted text-foreground border border-border font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />

        <TelegramLoginButton botUsername={BOT_USERNAME} onAuth={handleAuth} />

        {error && (
          <p className="text-destructive text-sm font-mono">{error}</p>
        )}
      </div>
    </div>
  )
}

export default LoginPage
