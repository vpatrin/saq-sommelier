import { useEffect, useState } from 'react'
import { useSearchParams, Navigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { api, ApiError } from '@/lib/api'

interface TokenResponse {
  access_token: string
}

function AuthCallbackPage() {
  const { t } = useTranslation()
  const { login, token } = useAuth()
  const [searchParams] = useSearchParams()
  const [error, setError] = useState<string | null>(null)

  const code = searchParams.get('code')

  useEffect(() => {
    if (!code || token) return

    api<TokenResponse>(`/auth/exchange?code=${encodeURIComponent(code)}`)
      .then(({ access_token }) => login(access_token))
      .catch((err) => {
        if (err instanceof ApiError) {
          setError(err.detail)
        } else {
          setError(t('authCallback.failed'))
        }
      })
  }, [code, token, login, t])

  if (token) return <Navigate to="/chat" replace />

  if (error) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-4">
        <p className="text-destructive text-sm">{error}</p>
        <a href="/login" className="text-sm text-primary hover:underline">
          {t('authCallback.backToLogin')}
        </a>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
      <p className="text-sm text-muted-foreground">{t('authCallback.loading')}</p>
    </div>
  )
}

export default AuthCallbackPage
