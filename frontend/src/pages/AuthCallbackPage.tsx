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
  const errorParam = searchParams.get('error')
  const isNew = searchParams.get('new') === '1'

  useEffect(() => {
    if (!code || token || errorParam) return

    const controller = new AbortController()
    api<TokenResponse>(`/auth/exchange?code=${encodeURIComponent(code)}`, {
      signal: controller.signal,
    })
      .then(({ access_token }) => {
        if (!isNew) localStorage.setItem('onboarded', '1')
        login(access_token)
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        if (err instanceof ApiError) {
          setError(err.detail)
        } else {
          setError(t('authCallback.failed'))
        }
      })

    return () => controller.abort()
  }, [code, token, login, t, errorParam, isNew])

  if (token) return <Navigate to={isNew ? '/onboarding' : '/chat'} replace />

  if (errorParam === 'not_approved') {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-4">
        <p className="text-sm text-muted-foreground">{t('authCallback.notApproved')}</p>
        <a href="/" className="text-sm text-primary hover:underline">
          {t('authCallback.requestAccess')}
        </a>
      </div>
    )
  }

  if (error || !code) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-4">
        <p className="text-destructive text-sm">{error ?? t('authCallback.failed')}</p>
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
