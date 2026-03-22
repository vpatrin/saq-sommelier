import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useMatch, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient } from '@/lib/api'
import { timeAgo } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { ChatSessionOut } from '@/lib/types'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

const NAV_ITEMS = [
  { to: '/search', labelKey: 'nav.search' },
  { to: '/watches', labelKey: 'nav.myWatches' },
  { to: '/stores', labelKey: 'nav.myStores' },
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
      <aside className="w-60 shrink-0 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col h-full">
        {/* Brand */}
        <div className="p-4 border-b border-sidebar-border">
          <Link to="/chat" className="text-lg font-mono font-bold text-primary">
            {t('brand')}
          </Link>
        </div>

        {/* Chat section — only when on /chat */}
        {isOnChat && (
          <div className="flex flex-col border-b border-sidebar-border">
            <button
              type="button"
              onClick={() => navigate('/chat')}
              className="mx-2 mt-2 mb-1 px-3 py-1.5 text-sm font-mono text-left border border-border hover:bg-sidebar-accent/50"
            >
              {t('nav.newChat')}
            </button>
            <div className="overflow-y-auto max-h-48 px-2 pb-2">
              {sessions.length === 0 && (
                <p className="px-3 py-1.5 text-xs text-muted-foreground">
                  {t('nav.noConversations')}
                </p>
              )}
              {sessions.map((session) => {
                const isActive = activeSessionId === String(session.id)
                const isConfirming = confirmDeleteId === session.id
                return (
                  <div
                    key={session.id}
                    className={`group flex items-center gap-1 px-3 py-1.5 text-sm font-mono ${
                      isActive
                        ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                        : 'hover:bg-sidebar-accent/50'
                    }`}
                  >
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
                        className="flex-1 min-w-0 bg-transparent border-b border-primary text-sm font-mono outline-none"
                      />
                    ) : (
                      <>
                        <Link
                          to={`/chat/${session.id}`}
                          className="flex-1 min-w-0 truncate"
                          title={session.title ?? t('nav.untitled')}
                          onDoubleClick={(e) => {
                            e.preventDefault()
                            setEditTitle(session.title ?? '')
                            setEditingId(session.id)
                          }}
                        >
                          {session.title ?? t('nav.untitled')}
                        </Link>
                        <span className="shrink-0 text-xs text-muted-foreground hidden group-hover:inline">
                          {timeAgo(session.updated_at, t)}
                        </span>
                        <button
                          type="button"
                          onClick={() => setConfirmDeleteId(session.id)}
                          className="shrink-0 text-xs text-muted-foreground hover:text-destructive hidden group-hover:inline"
                          title={t('nav.deleteSession')}
                        >
                          x
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
        <nav className="flex-1 p-2 flex flex-col gap-0.5">
          {/* Chat link — only when NOT on /chat (collapsed to single link) */}
          {!isOnChat && (
            <Link
              to="/chat"
              className="block px-3 py-2 text-sm font-mono transition-colors text-sidebar-foreground hover:bg-sidebar-accent/50"
            >
              {t('nav.chat')}
            </Link>
          )}
          {NAV_ITEMS.map(({ to, labelKey }) => {
            const active =
              location.pathname === to ||
              (to === '/stores' && location.pathname === '/stores/nearby')
            return (
              <Link
                key={to}
                to={to}
                className={`block px-3 py-2 text-sm font-mono transition-colors ${
                  active
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground font-bold'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                }`}
              >
                {t(labelKey)}
              </Link>
            )
          })}
        </nav>

        {/* Bottom section */}
        <div className="p-4 border-t border-sidebar-border flex flex-col gap-3">
          <a
            href={`https://t.me/${BOT_USERNAME}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground hover:text-primary font-mono"
          >
            @{BOT_USERNAME}
          </a>
          <div className="flex items-center gap-2 text-xs font-mono">
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
          <div className="flex items-center justify-between">
            <span className="text-sm font-mono truncate">{user?.first_name}</span>
            <Button variant="ghost" size="xs" className="w-20" onClick={handleLogout}>
              {t('nav.logout')}
            </Button>
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
