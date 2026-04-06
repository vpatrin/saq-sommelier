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
      <div className="max-w-[520px] mx-auto">
        <h1 className="text-[22px] font-light mb-7">
          <strong className="font-semibold">{t('settings.title')}</strong>
        </h1>

        {/* Compte */}
        <div className="mb-8">
          <p className="text-[10px] font-normal text-muted-foreground/40 uppercase tracking-wider mb-3.5 pl-0.5">
            {t('settings.account')}
          </p>
          <div className="rounded-xl border border-border bg-white/[0.025] overflow-hidden">
            {/* Display name */}
            <div className="flex items-center justify-between px-4.5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-primary/[0.06] border border-primary/10 flex items-center justify-center">
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
                  className="w-40 text-right text-sm bg-transparent border-b border-primary/20 text-foreground focus:outline-none"
                />
              ) : (
                <button
                  type="button"
                  onClick={() => setEditingName(true)}
                  className="text-sm text-muted-foreground hover:text-foreground transition-colors"
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
                  className="flex items-center justify-between px-4.5 py-3.5 border-t border-white/[0.03] group"
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-8 h-8 rounded-lg bg-white/[0.03] border border-white/[0.04] flex items-center justify-center">
                      {providerIcon(provider)}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm capitalize">{provider}</p>
                      {account && (
                        <p className="text-xs text-muted-foreground/40 truncate">{account.email}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {account ? (
                      <>
                        <span className="text-[11px] px-2.5 py-0.5 rounded-md bg-green-500/[0.08] border border-green-500/[0.12] text-green-400">
                          {t('settings.connected')}
                        </span>
                        {canDisconnect && (
                          <button
                            type="button"
                            onClick={() => handleDisconnect(provider)}
                            className="text-[11px] text-muted-foreground/30 hover:text-destructive opacity-0 group-hover:opacity-100 transition-all"
                          >
                            {t('settings.disconnect')}
                          </button>
                        )}
                      </>
                    ) : (
                      <a
                        href={`/api/auth/${provider}/login`}
                        className="text-[11px] px-2.5 py-0.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-primary/20 transition-colors"
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
          <p className="text-[10px] font-normal text-muted-foreground/40 uppercase tracking-wider mb-3.5 pl-0.5">
            {t('settings.preferences')}
          </p>
          <div className="rounded-xl border border-border bg-white/[0.025] overflow-hidden">
            <div className="flex items-center justify-between px-4.5 py-3.5">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/[0.03] border border-white/[0.04] flex items-center justify-center">
                  <GlobeIcon size={16} className="text-muted-foreground" />
                </div>
                <span className="text-sm">{t('settings.language')}</span>
              </div>
              <div className="flex rounded-lg border border-border overflow-hidden">
                {['fr', 'en'].map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => i18n.changeLanguage(lang)}
                    className={`px-3 py-1 text-xs font-mono uppercase transition-colors ${
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
          <p className="text-[10px] font-normal text-muted-foreground/40 uppercase tracking-wider mb-3.5 pl-0.5">
            {t('settings.notifications')}
          </p>
          <div className="rounded-xl border border-border bg-white/[0.025] overflow-hidden">
            <div className="flex items-center justify-between px-4.5 py-3.5 group">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-white/[0.03] border border-white/[0.04] flex items-center justify-center">
                  <TelegramLogoIcon size={16} className="text-muted-foreground" />
                </div>
                <div>
                  <p className="text-sm">Telegram</p>
                  <p className="text-xs text-muted-foreground/40">
                    {telegramLinked ? `@${BOT_USERNAME}` : t('settings.telegramDesc')}
                  </p>
                </div>
              </div>
              {telegramLinked ? (
                <div className="flex items-center gap-2">
                  <span className="text-[11px] px-2.5 py-0.5 rounded-md bg-green-500/[0.08] border border-green-500/[0.12] text-green-400">
                    {t('settings.connected')}
                  </span>
                  <button
                    type="button"
                    onClick={handleUnlinkTelegram}
                    className="text-[11px] text-muted-foreground/30 hover:text-destructive opacity-0 group-hover:opacity-100 transition-all"
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
          <p className="text-[10px] font-normal text-muted-foreground/40 uppercase tracking-wider mb-3.5 pl-0.5">
            {t('settings.dangerZone')}
          </p>
          <div className="rounded-xl border border-border bg-white/[0.025] overflow-hidden">
            <button
              type="button"
              onClick={() => setConfirmDelete(true)}
              className="flex items-center gap-3 px-4.5 py-3.5 w-full hover:bg-white/[0.01] transition-colors"
            >
              <div className="w-8 h-8 rounded-lg bg-destructive/[0.06] border border-destructive/10 flex items-center justify-center">
                <TrashIcon size={16} className="text-destructive" />
              </div>
              <div className="text-left">
                <p className="text-sm text-destructive">{t('settings.deleteAccount')}</p>
                <p className="text-xs text-muted-foreground/30">{t('settings.deleteDesc')}</p>
              </div>
            </button>
          </div>
        </div>

        {/* Footer */}
        <p className="text-center font-mono text-[10px] text-muted-foreground/30 pb-8">
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
          <div className="relative w-full max-w-sm mx-4 rounded-xl bg-[#0e0e12] border border-border shadow-2xl p-6">
            <p className="text-[14px] font-medium mb-1">{t('settings.deleteConfirmTitle')}</p>
            <p className="text-[13px] text-muted-foreground/50 mb-4">
              {t('settings.deleteConfirmDesc')}
            </p>
            <p className="text-[12px] text-muted-foreground/40 mb-2">
              {t('settings.deleteConfirmPrompt', { word: t('settings.deleteWord') })}
            </p>
            <input
              type="text"
              value={deleteInput}
              onChange={(e) => setDeleteInput(e.target.value)}
              placeholder={t('settings.deleteWord')}
              autoFocus
              className="w-full px-3 py-2 mb-4 rounded-lg border border-border bg-transparent text-sm text-foreground placeholder:text-muted-foreground/20 focus:border-destructive/30 focus:outline-none transition-colors"
            />
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  setConfirmDelete(false)
                  setDeleteInput('')
                }}
                className="text-[13px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
              >
                {t('settings.cancel')}
              </button>
              <button
                type="button"
                disabled={
                  deleting || deleteInput.toLowerCase() !== t('settings.deleteWord').toLowerCase()
                }
                onClick={handleDeleteAccount}
                className="px-4 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-[13px] font-medium hover:bg-destructive/90 disabled:opacity-50 transition-colors"
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
