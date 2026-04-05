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
          <a
            href="/api/auth/github/login"
            className="flex items-center justify-center gap-2 w-[320px] max-w-full h-10 rounded-lg bg-[#24292f] text-white text-sm font-medium hover:bg-[#2f363d] transition-colors"
          >
            <svg viewBox="0 0 16 16" className="w-5 h-5 fill-current" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            {t('login.github')}
          </a>

          <div className="flex items-center gap-3 w-[320px] max-w-full">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground">{t('login.or')}</span>
            <div className="flex-1 h-px bg-border" />
          </div>

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
