import { Navigate, Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import { WineIcon } from '@phosphor-icons/react'
import { useAuth } from '@/contexts/AuthContext'

function LoginPage() {
  const { t, i18n } = useTranslation()
  const { token } = useAuth()

  if (token) return <Navigate to="/chat" replace />

  return (
    <div className="bg-background text-foreground relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-8">
      {/* Ambient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="bg-primary/[0.06] absolute -top-32 -right-32 h-[500px] w-[500px] rounded-full blur-[120px]" />
        <div className="bg-primary/[0.03] absolute -bottom-32 -left-32 h-[400px] w-[400px] rounded-full blur-[100px]" />
      </div>

      {/* Lang toggle */}
      <button
        type="button"
        onClick={() => i18n.changeLanguage(i18n.resolvedLanguage === 'fr' ? 'en' : 'fr')}
        className="text-muted-foreground hover:text-foreground absolute top-4 right-6 w-8 text-center text-xs transition-colors"
      >
        {i18n.resolvedLanguage === 'fr' ? 'EN' : 'FR'}
      </button>

      <div className="relative flex w-full max-w-sm flex-col items-center gap-6">
        <div className="flex flex-col items-center gap-3">
          <div className="from-primary/35 to-primary/15 text-primary flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br shadow-[0_8px_32px_oklch(0.7_0.13_65_/_10%)]">
            <WineIcon size={32} />
          </div>
          <h1 className="text-2xl font-semibold">{t('brand')}</h1>
        </div>

        <div className="flex w-full flex-col items-center gap-3">
          <a
            href="/api/auth/google/login"
            className="focus-visible:ring-primary focus-visible:ring-offset-background flex h-10 w-[320px] max-w-full items-center justify-center gap-2 rounded-lg border border-[#dadce0] bg-white text-sm font-medium text-[#3c4043] transition-colors hover:bg-[#f8f9fa] focus-visible:ring-2 focus-visible:ring-offset-2"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5" aria-hidden="true">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            {t('login.google')}
          </a>

          <a
            href="/api/auth/github/login"
            className="focus-visible:ring-primary focus-visible:ring-offset-background flex h-10 w-[320px] max-w-full items-center justify-center gap-2 rounded-lg bg-[#24292f] text-sm font-medium text-white transition-colors hover:bg-[#2f363d] focus-visible:ring-2 focus-visible:ring-offset-2"
          >
            <svg viewBox="0 0 16 16" className="h-5 w-5 fill-current" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            {t('login.github')}
          </a>
        </div>

        <div className="mt-2 flex flex-col items-center gap-1.5">
          <div className="text-muted-foreground flex items-center gap-3 text-xs">
            <Link to="/" className="hover:text-foreground transition-colors">
              {t('login.backToLanding')}
            </Link>
            <span className="bg-border h-3 w-px" />
            <a
              href="https://www.educalcool.qc.ca/"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-foreground transition-colors"
            >
              Éduc'alcool
            </a>
          </div>
          <p className="text-muted-foreground text-center text-xs">{t('login.legal')}</p>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
