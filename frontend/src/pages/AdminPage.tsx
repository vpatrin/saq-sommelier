import { useEffect, useState } from 'react'
import { Navigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient } from '@/lib/api'
import type { WaitlistRequestOut, UserOut } from '@/lib/types'

type Tab = 'waitlist' | 'users'

const TAB_LABEL_KEYS: Record<Tab, string> = {
  waitlist: 'admin.tabWaitlist',
  users: 'admin.tabUsers',
}

export default function AdminPage() {
  const { user } = useAuth()
  const { t } = useTranslation()
  const [tab, setTab] = useState<Tab>('waitlist')

  if (user?.role !== 'admin') return <Navigate to="/chat" replace />

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="shrink-0 px-8 pt-8 pb-0 border-b border-border">
        <h1 className="text-xl font-semibold mb-4">{t('admin.title')}</h1>
        <div className="flex gap-1">
          {(['waitlist', 'users'] as Tab[]).map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setTab(id)}
              className={`px-4 py-2 text-sm rounded-t-lg transition-colors ${
                tab === id
                  ? 'bg-accent-glow text-primary border border-b-background border-border'
                  : 'text-muted-foreground hover:text-foreground'
              }`}
            >
              {t(TAB_LABEL_KEYS[id])}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-8">
        {tab === 'waitlist' ? <WaitlistTab /> : <UsersTab />}
      </div>
    </div>
  )
}

// ── Waitlist tab ──────────────────────────────────────────────────────────────

type WaitlistAction = 'approve' | 'reject' | 'resend'

function WaitlistTab() {
  const { t } = useTranslation()
  const apiClient = useApiClient()
  const [entries, setEntries] = useState<WaitlistRequestOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [rowLoading, setRowLoading] = useState<Record<number, boolean>>({})

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiClient<WaitlistRequestOut[]>('/admin/waitlist')
      .then((data) => {
        if (!cancelled) {
          setEntries(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(t('admin.waitlist.failedToLoad'))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [apiClient, t, retry])

  const handleAction = async (id: number, action: WaitlistAction) => {
    setRowLoading((prev) => ({ ...prev, [id]: true }))
    try {
      await apiClient(`/admin/waitlist/${id}/${action}`, { method: 'POST' })
      if (action === 'approve' || action === 'reject') {
        setEntries((prev) => prev.filter((e) => e.id !== id))
      } else {
        setEntries((prev) =>
          prev.map((e) => (e.id === id ? { ...e, email_sent_at: new Date().toISOString() } : e)),
        )
      }
    } catch {
      // Failure — leave row as-is
    } finally {
      setRowLoading((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
    }
  }

  if (loading) return <p className="text-muted-foreground text-sm">{t('chat.loading')}</p>
  if (error)
    return (
      <p className="text-destructive text-sm">
        {error}{' '}
        <button
          type="button"
          onClick={() => setRetry((n) => n + 1)}
          className="underline text-muted-foreground"
        >
          {t('admin.waitlist.retry')}
        </button>
      </p>
    )
  if (entries.length === 0)
    return <p className="text-muted-foreground text-sm">{t('admin.waitlist.empty')}</p>

  return (
    <div className="flex flex-col gap-2">
      {entries.map((entry) => {
        const busy = rowLoading[entry.id]
        return (
          <div
            key={entry.id}
            className="flex items-center gap-4 px-4 py-3 rounded-lg border border-border bg-card"
          >
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">{entry.email}</p>
              <p className="text-xs text-muted-foreground font-mono">
                {new Date(entry.created_at).toLocaleDateString()}
                {entry.email_sent_at && (
                  <span className="ml-2 text-primary/60">{t('admin.waitlist.emailSent')}</span>
                )}
                {entry.status === 'approved' && !entry.email_sent_at && (
                  <span className="ml-2 text-amber-500/60">{t('admin.waitlist.emailPending')}</span>
                )}
              </p>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {entry.status === 'pending' && (
                <>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleAction(entry.id, 'approve')}
                    className="px-3 py-1.5 text-xs rounded-lg bg-primary/10 text-primary border border-primary/20 hover:bg-primary/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {t('admin.waitlist.approve')}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => handleAction(entry.id, 'reject')}
                    className="px-3 py-1.5 text-xs rounded-lg text-muted-foreground border border-border hover:text-destructive hover:border-destructive/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {t('admin.waitlist.reject')}
                  </button>
                </>
              )}
              {entry.status === 'approved' && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => handleAction(entry.id, 'resend')}
                  className="px-3 py-1.5 text-xs rounded-lg text-muted-foreground border border-border hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {t('admin.waitlist.resend')}
                </button>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ── Users tab ─────────────────────────────────────────────────────────────────

function UsersTab() {
  const { t } = useTranslation()
  const apiClient = useApiClient()
  const [users, setUsers] = useState<UserOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retry, setRetry] = useState(0)
  const [rowErrors, setRowErrors] = useState<Record<number, string>>({})
  const [rowLoading, setRowLoading] = useState<Record<number, boolean>>({})
  const [confirmDelete, setConfirmDelete] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    apiClient<UserOut[]>('/admin/users')
      .then((data) => {
        if (!cancelled) {
          setUsers(data)
          setLoading(false)
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(t('admin.users.failedToLoad'))
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [apiClient, t, retry])

  const handleDelete = async (userId: number) => {
    setRowLoading((prev) => ({ ...prev, [userId]: true }))
    setRowErrors((prev) => {
      const copy = { ...prev }
      delete copy[userId]
      return copy
    })
    try {
      await apiClient(`/admin/users/${userId}`, { method: 'DELETE' })
      setUsers((prev) => prev.filter((u) => u.id !== userId))
    } catch {
      setRowErrors((prev) => ({ ...prev, [userId]: t('admin.users.failedToDelete') }))
    } finally {
      setConfirmDelete(null)
      setRowLoading((prev) => {
        const copy = { ...prev }
        delete copy[userId]
        return copy
      })
    }
  }

  const toggleActive = async (user: UserOut) => {
    if (user.role === 'admin') return
    const next = !user.is_active
    setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, is_active: next } : u)))
    setRowLoading((prev) => ({ ...prev, [user.id]: true }))
    setRowErrors((prev) => {
      const copy = { ...prev }
      delete copy[user.id]
      return copy
    })
    try {
      await apiClient(`/admin/users/${user.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: next }),
      })
    } catch {
      setUsers((prev) => prev.map((u) => (u.id === user.id ? { ...u, is_active: !next } : u)))
      setRowErrors((prev) => ({ ...prev, [user.id]: t('admin.users.failedToUpdate') }))
    } finally {
      setRowLoading((prev) => {
        const copy = { ...prev }
        delete copy[user.id]
        return copy
      })
    }
  }

  if (loading) return <p className="text-muted-foreground text-sm">{t('chat.loading')}</p>
  if (error)
    return (
      <p className="text-destructive text-sm">
        {error}{' '}
        <button
          type="button"
          onClick={() => setRetry((n) => n + 1)}
          className="underline text-muted-foreground"
        >
          {t('admin.users.retry')}
        </button>
      </p>
    )
  if (users.length === 0)
    return <p className="text-muted-foreground text-sm">{t('admin.users.empty')}</p>

  return (
    <>
      <div className="flex flex-col gap-2">
        {users.map((u) => (
          <div
            key={u.id}
            className="flex items-center gap-4 px-4 py-3 rounded-lg border border-border bg-card"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium truncate">{u.display_name ?? u.email}</p>
                {u.role === 'admin' && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded border border-primary/20 bg-primary/10 text-primary font-mono">
                    {t('admin.users.admin')}
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3">
                <p className="text-xs text-muted-foreground font-mono">
                  {u.last_login_at
                    ? new Date(u.last_login_at).toLocaleDateString()
                    : new Date(u.created_at).toLocaleDateString()}
                </p>
                {rowErrors[u.id] && <p className="text-xs text-destructive">{rowErrors[u.id]}</p>}
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span
                className={`text-xs font-mono ${u.is_active ? 'text-primary/60' : 'text-muted-foreground/40'}`}
              >
                {u.is_active ? t('admin.users.active') : t('admin.users.inactive')}
              </span>
              {u.role !== 'admin' && (
                <>
                  <button
                    type="button"
                    disabled={rowLoading[u.id]}
                    onClick={() => toggleActive(u)}
                    className={`px-3 py-1.5 text-xs rounded-lg border transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
                      u.is_active
                        ? 'text-muted-foreground border-border hover:text-destructive hover:border-destructive/30'
                        : 'text-primary border-primary/20 bg-primary/10 hover:bg-primary/20'
                    }`}
                  >
                    {u.is_active ? t('admin.users.deactivate') : t('admin.users.activate')}
                  </button>
                  <button
                    type="button"
                    disabled={rowLoading[u.id]}
                    onClick={() => setConfirmDelete(u.id)}
                    className="px-3 py-1.5 text-xs rounded-lg text-muted-foreground border border-border hover:text-destructive hover:border-destructive/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {t('admin.users.delete')}
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {confirmDelete !== null && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setConfirmDelete(null)}
          />
          <div className="relative w-full max-w-sm mx-4 rounded-xl bg-[#0e0e12] border border-border shadow-2xl p-6">
            <p className="text-[14px] font-medium mb-1">{t('admin.users.confirmDeleteTitle')}</p>
            <p className="text-[13px] text-muted-foreground/50 mb-6">
              {t('admin.users.confirmDeleteDesc')}
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDelete(null)}
                className="text-[13px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
              >
                {t('noteView.cancel')}
              </button>
              <button
                type="button"
                disabled={rowLoading[confirmDelete]}
                onClick={() => handleDelete(confirmDelete)}
                className="px-4 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-[13px] font-medium hover:bg-destructive/90 disabled:opacity-50 transition-colors"
              >
                {t('admin.users.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
