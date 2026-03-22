import { useState, useCallback } from 'react'
import { useNavigate, useParams, Navigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { TelegramLoginButton, type TelegramLoginData } from '@/components/TelegramLoginButton'
import { api, ApiError } from '@/lib/api'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

interface TokenResponse {
  access_token: string
  token_type: string
}

function LoginPage() {
  const { t } = useTranslation()
  const { token, login } = useAuth()
  const navigate = useNavigate()
  const { code } = useParams<{ code: string }>()
  const [error, setError] = useState<string | null>(null)

  const handleAuth = useCallback(
    async (telegramData: TelegramLoginData) => {
      setError(null)
      try {
        const body = {
          ...telegramData,
          ...(code ? { invite_code: code } : {}),
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
          setError(t('login.authFailed'))
        }
      }
    },
    [code, login, navigate, t],
  )

  if (token) return <Navigate to="/dashboard" replace />

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-8 p-8">
      <div className="flex flex-col items-center gap-2">
        <h1 className="text-5xl font-mono font-bold">{t('brand')} 🥂</h1>
        <p className="text-muted-foreground">{t('login.tagline')}</p>
      </div>

      {code && (
        <p className="text-sm text-primary font-mono border border-primary px-4 py-2">
          {t('login.invited')}
        </p>
      )}

      <div className="flex flex-col items-center gap-4">
        <TelegramLoginButton botUsername={BOT_USERNAME} onAuth={handleAuth} />

        {error && (
          <p className="text-destructive text-sm font-mono max-w-xs text-center">{error}</p>
        )}
      </div>

      <footer className="text-xs text-muted-foreground flex flex-col items-center gap-1 mt-4">
        <p>{t('login.madeWith')}</p>
        <a
          href="https://github.com/vpatrin/coupette"
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary underline underline-offset-2"
        >
          {t('login.sourceOnGithub')}
        </a>
      </footer>
    </div>
  )
}

export default LoginPage
