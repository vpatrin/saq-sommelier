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
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center p-8 relative overflow-hidden">
      {/* Lang toggle */}
      <button
        type="button"
        onClick={() => i18n.changeLanguage(i18n.resolvedLanguage === 'fr' ? 'en' : 'fr')}
        className="absolute top-4 right-6 w-8 text-center text-xs text-muted-foreground hover:text-foreground transition-colors"
      >
        {i18n.resolvedLanguage === 'fr' ? 'EN' : 'FR'}
      </button>

      {/* Ambient orbs */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -right-32 w-[500px] h-[500px] rounded-full bg-primary/[0.06] blur-[120px]" />
        <div className="absolute -bottom-32 -left-32 w-[400px] h-[400px] rounded-full bg-primary/[0.03] blur-[100px]" />
      </div>

      <div className="relative flex flex-col items-center gap-6 w-full max-w-sm">
        <div className="flex flex-col items-center gap-3">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary/35 to-primary/15 flex items-center justify-center text-primary shadow-[0_8px_32px_oklch(0.7_0.13_65_/_10%)]">
            <WineIcon size={32} />
          </div>
        </div>

        <div className="flex flex-col items-center gap-2">
          <h1 className="text-[22px] font-light">{t('onboarding.nameTitle')}</h1>
          <p className="text-[13px] font-light text-muted-foreground/40">
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
          className="w-full max-w-[300px] px-5 py-3.5 rounded-xl border border-border bg-white/[0.02] text-center text-base text-foreground placeholder:text-muted-foreground/30 placeholder:text-sm placeholder:font-light focus:border-primary/20 focus:outline-none transition-colors"
        />

        <button
          type="button"
          disabled={!name.trim() || saving}
          onClick={handleSubmit}
          className="px-9 py-3 rounded-xl bg-gradient-to-br from-primary/25 to-primary/15 border border-primary/20 text-[15px] font-medium text-primary hover:from-primary/35 hover:to-primary/25 hover:shadow-[0_0_24px_rgba(200,146,72,0.1)] disabled:opacity-30 disabled:cursor-default disabled:hover:shadow-none transition-all"
        >
          {t('onboarding.continue')}
        </button>

        {error && <p className="text-destructive text-sm">{t('onboarding.error')}</p>}
      </div>
    </div>
  )
}

export default OnboardingPage
