import { useState } from 'react'
import { useNavigate, Navigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { WineIcon } from '@phosphor-icons/react'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient } from '@/lib/api'

function OnboardingPage() {
  const { t, i18n } = useTranslation()
  const { user, token, updateUser } = useAuth()
  const navigate = useNavigate()
  const apiClient = useApiClient()
  const [name, setName] = useState(user?.display_name ?? '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(false)

  if (!token) return <Navigate to="/login" replace />

  const handleSubmit = async () => {
    const trimmed = name.trim()
    if (!trimmed) return
    setSaving(true)
    setError(false)
    const locale = i18n.resolvedLanguage === 'en' ? 'en' : 'fr'
    try {
      await apiClient('/users/me', {
        method: 'PATCH',
        body: JSON.stringify({ display_name: trimmed, locale }),
      })
      updateUser({ display_name: trimmed, locale })
      localStorage.setItem('onboarded', '1')
      navigate('/chat', { replace: true })
    } catch {
      setError(true)
      setSaving(false)
    }
  }

  return (
    <div className="bg-background text-foreground relative flex min-h-screen flex-col items-center justify-center overflow-hidden p-8">
      {/* Lang toggle */}
      <button
        type="button"
        onClick={() => i18n.changeLanguage(i18n.resolvedLanguage === 'fr' ? 'en' : 'fr')}
        className="text-muted-foreground hover:text-foreground absolute top-4 right-6 w-8 text-center text-xs transition-colors"
      >
        {i18n.resolvedLanguage === 'fr' ? 'EN' : 'FR'}
      </button>

      {/* Ambient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="bg-primary/[0.06] absolute -top-32 -right-32 h-[500px] w-[500px] rounded-full blur-[120px]" />
        <div className="bg-primary/[0.03] absolute -bottom-32 -left-32 h-[400px] w-[400px] rounded-full blur-[100px]" />
      </div>

      <div className="relative flex w-full max-w-sm flex-col items-center gap-6">
        <div className="flex flex-col items-center gap-3">
          <div className="from-primary/35 to-primary/15 text-primary flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br shadow-[0_8px_32px_oklch(0.7_0.13_65_/_10%)]">
            <WineIcon size={32} />
          </div>
        </div>

        <div className="flex flex-col items-center gap-2">
          <h1 className="text-[22px] font-light">{t('onboarding.nameTitle')}</h1>
          <p className="text-muted-foreground/40 text-[13px] font-light">
            {t('onboarding.nameSub')}
          </p>
        </div>

        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && name.trim()) handleSubmit()
          }}
          placeholder={t('onboarding.namePlaceholder')}
          maxLength={100}
          autoFocus
          className="border-border text-foreground placeholder:text-muted-foreground/30 focus:border-primary/20 w-full max-w-[300px] rounded-xl border bg-white/[0.02] px-5 py-3.5 text-center text-base transition-colors placeholder:text-sm placeholder:font-light focus:outline-none"
        />

        <button
          type="button"
          disabled={!name.trim() || saving}
          onClick={handleSubmit}
          className="from-primary/25 to-primary/15 border-primary/20 text-primary hover:from-primary/35 hover:to-primary/25 rounded-xl border bg-gradient-to-br px-9 py-3 text-[15px] font-medium transition-all hover:shadow-[0_0_24px_rgba(200,146,72,0.1)] disabled:cursor-default disabled:opacity-30 disabled:hover:shadow-none"
        >
          {t('onboarding.continue')}
        </button>

        {error && <p className="text-destructive text-sm">{t('onboarding.error')}</p>}
      </div>
    </div>
  )
}

export default OnboardingPage
