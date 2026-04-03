import { useState } from 'react'
import { useNavigate, Navigate, Link } from 'react-router'
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
  const { t, i18n } = useTranslation()
  const { token, login } = useAuth()
  const navigate = useNavigate()
  const [error, setError] = useState<string | null>(null)

  const handleAuth = async (telegramData: TelegramLoginData) => {
    setError(null)
    try {
      const { access_token } = await api<TokenResponse>('/auth/telegram', {
        method: 'POST',
        body: JSON.stringify(telegramData),
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
  }

  if (token) return <Navigate to="/chat" replace />

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Ambient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -right-32 w-[500px] h-[500px] rounded-full bg-primary/[0.06] blur-[120px]" />
        <div className="absolute -bottom-32 -left-32 w-[400px] h-[400px] rounded-full bg-primary/[0.03] blur-[100px]" />
      </div>

      {/* Lang toggle */}
      <button
        type="button"
        onClick={() => i18n.changeLanguage(i18n.resolvedLanguage === 'fr' ? 'en' : 'fr')}
        className="absolute top-4 right-6 w-8 text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {i18n.resolvedLanguage === 'fr' ? 'EN' : 'FR'}
      </button>

      <div className="relative flex flex-col items-center gap-6 w-full max-w-sm">
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/35 to-primary/15 flex items-center justify-center text-2xl font-semibold text-primary shadow-[0_8px_32px_oklch(0.7_0.13_65_/_10%)]">
            C
          </div>
          <h1 className="text-2xl font-semibold">{t('brand')}</h1>
        </div>

        <div className="flex flex-col items-center gap-3 w-full">
          <div className="w-[320px] max-w-full flex justify-center overflow-hidden">
            <TelegramLoginButton
              botUsername={BOT_USERNAME}
              onAuth={handleAuth}
              lang={i18n.resolvedLanguage}
            />
          </div>
          {error && <p className="text-destructive text-sm text-center">{error}</p>}
        </div>

        <div className="flex flex-col items-center gap-1.5 mt-2">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            <Link to="/" className="hover:text-foreground transition-colors">
              {t('login.backToLanding')}
            </Link>
            <span className="w-px h-3 bg-border" />
            <a
              href="https://www.educalcool.qc.ca/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Éduc'alcool
            </a>
          </div>
          <p className="text-xs text-muted-foreground text-center">{t('login.legal')}</p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
