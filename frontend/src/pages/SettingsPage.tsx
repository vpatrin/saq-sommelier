import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  UserIcon,
  GithubLogoIcon,
  GoogleLogoIcon,
  GlobeIcon,
  TrashIcon,
  TelegramLogoIcon,
} from '@phosphor-icons/react'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient } from '@/lib/api'
import type { OAuthAccountOut } from '@/lib/types'
import { TelegramLoginButton, type TelegramLoginData } from '@/components/TelegramLoginButton'

const PROVIDERS = ['github', 'google'] as const
const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

function SettingsPage() {
  const { t, i18n } = useTranslation()
  const { user, updateUser, logout } = useAuth()
  const navigate = useNavigate()
  const apiClient = useApiClient()

  const [accounts, setAccounts] = useState<OAuthAccountOut[]>([])
  const [editingName, setEditingName] = useState(false)
  const [nameValue, setNameValue] = useState(user?.display_name ?? '')
  const [savingName, setSavingName] = useState(false)
  const [telegramLinked, setTelegramLinked] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteInput, setDeleteInput] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (!confirmDelete) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setConfirmDelete(false)
        setDeleteInput('')
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [confirmDelete])

  useEffect(() => {
    const controller = new AbortController()
    apiClient<OAuthAccountOut[]>('/users/me/accounts', { signal: controller.signal })
      .then(setAccounts)
      .catch(() => {})
    apiClient<{ linked: boolean }>('/users/me/telegram', { signal: controller.signal })
      .then((r) => setTelegramLinked(r.linked))
      .catch(() => {})
    return () => controller.abort()
  }, [apiClient])

  const handleSaveName = async () => {
    if (savingName) return
    const trimmed = nameValue.trim()
    if (!trimmed || trimmed === user?.display_name) {
      setEditingName(false)
      return
    }
    setSavingName(true)
    try {
      await apiClient('/users/me', {
        method: 'PATCH',
        body: JSON.stringify({ display_name: trimmed }),
      })
      updateUser({ display_name: trimmed })
      setEditingName(false)
    } catch {
      // Keep editing on error
    } finally {
      setSavingName(false)
    }
  }

  const handleDisconnect = async (provider: string) => {
    try {
      await apiClient(`/users/me/accounts/${provider}`, { method: 'DELETE' })
      setAccounts((prev) => prev.filter((a) => a.provider !== provider))
    } catch {
      // 409 = last account — silently ignore
    }
  }

  const handleLinkTelegram = async (data: TelegramLoginData) => {
    try {
      await apiClient('/users/me/telegram', {
        method: 'POST',
        body: JSON.stringify(data),
      })
      setTelegramLinked(true)
    } catch {
      // Conflict (409) = already linked to another user
    }
  }

  const handleUnlinkTelegram = async () => {
    try {
      await apiClient('/users/me/telegram', { method: 'DELETE' })
      setTelegramLinked(false)
    } catch {
      // silently ignore
    }
  }

  const handleDeleteAccount = async () => {
    setDeleting(true)
    try {
      await apiClient('/users/me', { method: 'DELETE' })
      localStorage.removeItem('onboarded')
      logout()
      navigate('/', { replace: true })
    } catch {
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  const canDisconnect = accounts.length > 1

  const providerIcon = (provider: string) => {
    if (provider === 'github') return <GithubLogoIcon size={16} className="text-foreground" />
    return <GoogleLogoIcon size={16} />
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="mx-auto max-w-[520px]">
        <h1 className="mb-7 text-[22px] font-light">
          <strong className="font-semibold">{t('settings.title')}</strong>
        </h1>

        {/* Compte */}
        <div className="mb-8">
          <p className="text-muted-foreground/40 mb-3.5 pl-0.5 text-[10px] font-normal tracking-wider uppercase">
            {t('settings.account')}
          </p>
          <div className="border-border overflow-hidden rounded-xl border bg-white/[0.025]">
            {/* Display name */}
            <div className="flex items-center justify-between px-4.5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="bg-primary/[0.06] border-primary/10 flex h-8 w-8 items-center justify-center rounded-lg border">
                  <UserIcon size={16} className="text-primary" />
                </div>
                <span className="text-sm">{t('settings.displayName')}</span>
              </div>
              {editingName ? (
                <input
                  type="text"
                  value={nameValue}
                  onChange={(e) => setNameValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleSaveName()
                    if (e.key === 'Escape') {
                      setNameValue(user?.display_name ?? '')
                      setEditingName(false)
                    }
                  }}
                  onBlur={handleSaveName}
                  disabled={savingName}
                  autoFocus
                  maxLength={100}
                  className="border-primary/20 text-foreground w-40 border-b bg-transparent text-right text-sm focus:outline-none"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setEditingName(true)}
                  className="text-muted-foreground hover:text-foreground text-sm transition-colors"
                >
                  {user?.display_name ?? '—'}
                </button>
              )}
            </div>

            {/* Linked accounts */}
            {PROVIDERS.map((provider) => {
              const account = accounts.find((a) => a.provider === provider)
              return (
                <div
                  key={provider}
                  className="group flex items-center justify-between border-t border-white/[0.03] px-4.5 py-3.5"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.04] bg-white/[0.03]">
                      {providerIcon(provider)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm capitalize">{provider}</p>
                      {account && (
                        <p className="text-muted-foreground/40 truncate text-xs">{account.email}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {account ? (
                      <>
                        <span className="rounded-md border border-green-500/[0.12] bg-green-500/[0.08] px-2.5 py-0.5 text-[11px] text-green-400">
                          {t('settings.connected')}
                        </span>
                        {canDisconnect && (
                          <button
                            type="button"
                            onClick={() => handleDisconnect(provider)}
                            className="text-muted-foreground/30 hover:text-destructive text-[11px] opacity-0 transition-all group-hover:opacity-100"
                          >
                            {t('settings.disconnect')}
                          </button>
                        )}
                      </>
                    ) : (
                      <a
                        href={`/api/auth/${provider}/login`}
                        className="border-border text-muted-foreground hover:text-foreground hover:border-primary/20 rounded-md border px-2.5 py-0.5 text-[11px] transition-colors"
                      >
                        {t('settings.connect')}
                      </a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Préférences */}
        <div className="mb-8">
          <p className="text-muted-foreground/40 mb-3.5 pl-0.5 text-[10px] font-normal tracking-wider uppercase">
            {t('settings.preferences')}
          </p>
          <div className="border-border overflow-hidden rounded-xl border bg-white/[0.025]">
            <div className="flex items-center justify-between px-4.5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.04] bg-white/[0.03]">
                  <GlobeIcon size={16} className="text-muted-foreground" />
                </div>
                <span className="text-sm">{t('settings.language')}</span>
              </div>
              <div className="border-border flex overflow-hidden rounded-lg border">
                {(['fr', 'en'] as const).map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={async () => {
                      if (lang === user?.locale) return
                      updateUser({ locale: lang })
                      try {
                        await apiClient('/users/me', {
                          method: 'PATCH',
                          body: JSON.stringify({ locale: lang }),
                        })
                      } catch {
                        // Best-effort — locale already applied locally
                      }
                    }}
                    className={`px-3 py-1 font-mono text-xs uppercase transition-colors ${
                      i18n.resolvedLanguage === lang
                        ? 'bg-primary/10 text-primary border-primary/20'
                        : 'text-muted-foreground/40 hover:text-muted-foreground'
                    }`}
                  >
                    {lang}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="mb-8">
          <p className="text-muted-foreground/40 mb-3.5 pl-0.5 text-[10px] font-normal tracking-wider uppercase">
            {t('settings.notifications')}
          </p>
          <div className="border-border overflow-hidden rounded-xl border bg-white/[0.025]">
            <div className="group flex items-center justify-between px-4.5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.04] bg-white/[0.03]">
                  <TelegramLogoIcon size={16} className="text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm">Telegram</p>
                  <p className="text-muted-foreground/40 text-xs">
                    {telegramLinked ? `@${BOT_USERNAME}` : t('settings.telegramDesc')}
                  </p>
                </div>
              </div>
              {telegramLinked ? (
                <div className="flex items-center gap-2">
                  <span className="rounded-md border border-green-500/[0.12] bg-green-500/[0.08] px-2.5 py-0.5 text-[11px] text-green-400">
                    {t('settings.connected')}
                  </span>
                  <button
                    type="button"
                    onClick={handleUnlinkTelegram}
                    className="text-muted-foreground/30 hover:text-destructive text-[11px] opacity-0 transition-all group-hover:opacity-100"
                  >
                    {t('settings.disconnect')}
                  </button>
                </div>
              ) : (
                <TelegramLoginButton
                  botUsername={BOT_USERNAME}
                  onAuth={handleLinkTelegram}
                  lang={i18n.resolvedLanguage}
                />
              )}
            </div>
          </div>
        </div>

        {/* Zone dangereuse */}
        <div className="mb-8">
          <p className="text-muted-foreground/40 mb-3.5 pl-0.5 text-[10px] font-normal tracking-wider uppercase">
            {t('settings.dangerZone')}
          </p>
          <div className="border-border overflow-hidden rounded-xl border bg-white/[0.025]">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="flex w-full items-center gap-3 px-4.5 py-3.5 transition-colors hover:bg-white/[0.01]"
            >
              <div className="bg-destructive/[0.06] border-destructive/10 flex h-8 w-8 items-center justify-center rounded-lg border">
                <TrashIcon size={16} className="text-destructive" />
              </div>
              <div className="text-left">
                <p className="text-destructive text-sm">{t('settings.deleteAccount')}</p>
                <p className="text-muted-foreground/30 text-xs">{t('settings.deleteDesc')}</p>
              </div>
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-muted-foreground/30 pb-8 text-center font-mono text-[10px]">
          Coupette · Montréal, QC
        </p>
      </div>

      {/* Delete confirmation dialog */}
      {confirmDelete && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setConfirmDelete(false)}
          />
          <div className="border-border relative mx-4 w-full max-w-sm rounded-xl border bg-[#0e0e12] p-6 shadow-2xl">
            <p className="mb-1 text-[14px] font-medium">{t('settings.deleteConfirmTitle')}</p>
            <p className="text-muted-foreground/50 mb-4 text-[13px]">
              {t('settings.deleteConfirmDesc')}
            </p>
            <p className="text-muted-foreground/40 mb-2 text-[12px]">
              {t('settings.deleteConfirmPrompt', { word: t('settings.deleteWord') })}
            </p>
            <input
              type="text"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              placeholder={t('settings.deleteWord')}
              autoFocus
              className="border-border text-foreground placeholder:text-muted-foreground/20 focus:border-destructive/30 mb-4 w-full rounded-lg border bg-transparent px-3 py-2 text-sm transition-colors focus:outline-none"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  setConfirmDelete(false)
                  setDeleteInput('')
                }}
                className="text-muted-foreground/50 hover:text-muted-foreground text-[13px] transition-colors"
              >
                {t('settings.cancel')}
              </button>
              <button
                type="button"
                disabled={
                  deleting || deleteInput.toLowerCase() !== t('settings.deleteWord').toLowerCase()
                }
                onClick={handleDeleteAccount}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90 rounded-lg px-4 py-1.5 text-[13px] font-medium transition-colors disabled:opacity-50"
              >
                {t('settings.deleteButton')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default SettingsPage
