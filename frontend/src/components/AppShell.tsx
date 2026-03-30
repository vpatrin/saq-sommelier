import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useMatch, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient } from '@/lib/api'
import { timeAgo } from '@/lib/utils'
import {
  Clock,
  MagnifyingGlass,
  Eye,
  MapPin,
  ChatCircle,
  Plus,
  X,
  SignOutIcon,
} from '@phosphor-icons/react'
import type { ChatSessionOut } from '@/lib/types'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

const NAV_ITEMS = [
  { to: '/search', labelKey: 'nav.search', icon: MagnifyingGlass },
  { to: '/watches', labelKey: 'nav.myWatches', icon: Eye },
  { to: '/stores', labelKey: 'nav.myStores', icon: MapPin },
] as const

export interface ChatOutletContext {
  refreshSessions: () => void
}

function AppShell() {
  const { t, i18n } = useTranslation()
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const apiClient = useApiClient()

  const isOnChat = location.pathname.startsWith('/chat')
  const sessionMatch = useMatch('/chat/:sessionId')
  const activeSessionId = sessionMatch?.params.sessionId ?? null

  const [sessions, setSessions] = useState<ChatSessionOut[]>([])
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const renamingRef = useRef(false)

  const handleLogout = useCallback(() => {
    logout()
    navigate('/', { replace: true })
  }, [logout, navigate])

  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiClient<ChatSessionOut[]>('/chat/sessions')
      setSessions(data)
    } catch {
      // Silently fail — sidebar is non-critical
    }
  }, [apiClient])

  // Load sessions when navigating to chat
  useEffect(() => {
    if (!isOnChat) return
    let cancelled = false
    apiClient<ChatSessionOut[]>('/chat/sessions')
      .then((data) => {
        if (!cancelled) setSessions(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isOnChat, apiClient])

  const handleRename = async (id: number) => {
    if (renamingRef.current) return
    renamingRef.current = true
    const trimmed = editTitle.trim()
    if (!trimmed) {
      setEditingId(null)
      renamingRef.current = false
      return
    }
    try {
      const updated = await apiClient<ChatSessionOut>(`/chat/sessions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: trimmed }),
      })
      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)))
    } catch {
      // Silently fail
    }
    setEditingId(null)
    renamingRef.current = false
  }

  const handleDelete = async (id: number) => {
    try {
      await apiClient(`/chat/sessions/${id}`, { method: 'DELETE' })
      setSessions((prev) => prev.filter((s) => s.id !== id))
      setConfirmDeleteId(null)
      if (activeSessionId === String(id)) {
        navigate('/chat', { replace: true })
      }
    } catch {
      // Silently fail
    }
  }

  const outletContext = useMemo<ChatOutletContext>(
    () => ({ refreshSessions: fetchSessions }),
    [fetchSessions],
  )

  return (
    <div className="h-screen bg-background text-foreground flex">
      {/* Sidebar */}
      <aside className="w-65 shrink-0 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col h-full">
        {/* Brand */}
        <div className="px-[var(--spacing-sidebar-x)] pt-5 pb-3.5">
          <Link to="/chat" className="flex items-center gap-2.5">
            <div className="w-7.5 h-7.5 rounded-lg bg-gradient-to-br from-primary/35 to-primary/15 flex items-center justify-center text-sm font-semibold text-primary shrink-0">
              C
            </div>
            <span className="text-base font-medium text-foreground">{t('brand')}</span>
          </Link>

          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="mt-4 flex items-center gap-2 w-full px-3.5 py-2 rounded-lg border border-border bg-transparent text-[length:var(--text-sidebar)] font-light text-muted-foreground hover:border-border-warm hover:text-sidebar-foreground hover:bg-accent-glow transition-colors"
          >
            <Plus size={16} weight="regular" className="text-muted-foreground" />
            {t('nav.newChat')}
          </button>
        </div>

        {/* Chat history — only when on /chat */}
        {isOnChat && sessions.length > 0 && (
          <div className="border-b border-sidebar-border">
            <div className="px-[var(--spacing-sidebar-x)] pt-3 pb-1.5 flex items-center gap-1.5 text-[length:var(--text-sidebar-xs)] font-normal tracking-wider uppercase text-muted-foreground">
              <Clock size={14} className="opacity-70" />
              {t('nav.history')}
            </div>
            <div className="overflow-y-auto max-h-48 pb-2">
              {sessions.map((session) => {
                const isActive = activeSessionId === String(session.id)
                const isConfirming = confirmDeleteId === session.id
                return (
                  <div
                    key={session.id}
                    className={`group relative flex items-center gap-1 px-[var(--spacing-sidebar-x)] py-1.5 text-[length:var(--text-sidebar)] ${
                      isActive ? 'bg-accent-glow' : 'hover:bg-surface-hover'
                    }`}
                  >
                    {isActive && (
                      <div className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-r bg-primary" />
                    )}
                    {isConfirming ? (
                      <div className="flex-1 flex items-center gap-2 min-w-0">
                        <span className="text-xs text-muted-foreground truncate">
                          {t('nav.deleteConfirm')}
                        </span>
                        <button
                          type="button"
                          onClick={() => handleDelete(session.id)}
                          className="text-xs text-destructive hover:text-destructive/80"
                        >
                          {t('nav.yes')}
                        </button>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(null)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          {t('nav.no')}
                        </button>
                      </div>
                    ) : editingId === session.id ? (
                      <input
                        autoFocus
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') handleRename(session.id)
                          if (e.key === 'Escape') setEditingId(null)
                        }}
                        onBlur={() => handleRename(session.id)}
                        maxLength={50}
                        className="flex-1 min-w-0 bg-transparent border-b border-primary text-sm outline-none"
                      />
                    ) : (
                      <>
                        <Link
                          to={`/chat/${session.id}`}
                          className={`flex-1 min-w-0 truncate ${isActive ? 'text-primary' : 'text-muted-foreground'}`}
                          title={session.title ?? t('nav.untitled')}
                          onDoubleClick={(e) => {
                            e.preventDefault()
                            setEditTitle(session.title ?? '')
                            setEditingId(session.id)
                          }}
                        >
                          {session.title ?? t('nav.untitled')}
                        </Link>
                        <span className="shrink-0 text-[length:var(--text-sidebar-xs)] font-mono text-muted-foreground hidden group-hover:inline">
                          {timeAgo(session.updated_at, t)}
                        </span>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(session.id)}
                          className="shrink-0 text-xs text-muted-foreground hover:text-destructive hidden group-hover:inline"
                          title={t('nav.deleteSession')}
                        >
                          <X size={12} />
                        </button>
                      </>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 px-2 py-2 flex flex-col gap-0.5">
          {/* Chat link — only when NOT on /chat */}
          {!isOnChat && (
            <Link
              to="/chat"
              className="flex items-center gap-2.5 px-3 py-2 text-[length:var(--text-sidebar)] rounded-lg transition-colors text-sidebar-foreground hover:bg-surface-hover"
            >
              <ChatCircle size={16} className="opacity-70" />
              {t('nav.chat')}
            </Link>
          )}
          {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => {
            const active =
              location.pathname === to ||
              (to === '/stores' && location.pathname === '/stores/nearby')
            return (
              <Link
                key={to}
                to={to}
                className={`relative flex items-center gap-2.5 px-3 py-2 text-[length:var(--text-sidebar)] rounded-lg transition-colors ${
                  active
                    ? 'bg-accent-glow text-primary'
                    : 'text-sidebar-foreground hover:bg-surface-hover'
                }`}
              >
                <Icon size={16} weight={active ? 'fill' : 'regular'} className="opacity-70" />
                {t(labelKey)}
              </Link>
            )
          })}
        </nav>

        {/* Profile trigger at bottom */}
        <div className="mt-auto border-t border-sidebar-border px-4 py-3.5">
          <div className="flex items-center gap-2 text-xs mb-3">
            <button
              type="button"
              onClick={() => i18n.changeLanguage('fr')}
              className={
                i18n.resolvedLanguage === 'fr'
                  ? 'text-primary font-bold'
                  : 'text-muted-foreground hover:text-foreground'
              }
            >
              FR
            </button>
            <span className="text-muted-foreground">·</span>
            <button
              type="button"
              onClick={() => i18n.changeLanguage('en')}
              className={
                i18n.resolvedLanguage === 'en'
                  ? 'text-primary font-bold'
                  : 'text-muted-foreground hover:text-foreground'
              }
            >
              EN
            </button>
          </div>
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-primary/15 border border-primary/20 flex items-center justify-center text-[length:var(--text-sidebar)] font-medium text-primary shrink-0">
              {user?.first_name?.charAt(0) ?? '?'}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-[length:var(--text-sidebar)] font-medium truncate">{user?.first_name}</div>
              <a
                href={`https://t.me/${BOT_USERNAME}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[length:var(--text-sidebar-xs)] text-muted-foreground hover:text-primary"
              >
                @{BOT_USERNAME}
              </a>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="text-muted-foreground hover:text-foreground transition-colors"
              title={t('nav.logout')}
              aria-label={t('nav.logout')}
            >
              <SignOutIcon size={14} />
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <Outlet context={outletContext} />
      </main>
    </div>
  )
}

export default AppShell
