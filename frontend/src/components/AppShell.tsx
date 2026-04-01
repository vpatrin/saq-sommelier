import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, Outlet, useLocation, useMatch, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient } from '@/lib/api'
import {
  MagnifyingGlassIcon as MagnifyingGlass,
  EyeIcon as Eye,
  MapPinIcon as MapPin,
  ChatCircleIcon as ChatCircle,
  PlusIcon as Plus,
  DotsThreeIcon as DotsThree,
  PencilSimpleIcon as PencilSimple,
  TrashIcon as Trash,
  SignOutIcon,
  WineIcon,
} from '@phosphor-icons/react'
import type { ChatSessionOut } from '@/lib/types'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

const NAV_ITEMS = [
  { to: '/chats', labelKey: 'nav.chat', icon: ChatCircle },
  { to: '/search', labelKey: 'nav.search', icon: MagnifyingGlass },
  { to: '/watches', labelKey: 'nav.myWatches', icon: Eye },
  { to: '/stores', labelKey: 'nav.myStores', icon: MapPin },
] as const

export interface ChatOutletContext {
  refreshSessions: () => void
  sessions: ChatSessionOut[]
  renameSession: (id: number, title: string) => Promise<void>
  deleteSession: (id: number) => Promise<void>
}

function AppShell() {
  const { t, i18n } = useTranslation()
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const apiClient = useApiClient()

  const sessionMatch = useMatch('/chat/:sessionId')
  const activeSessionId = sessionMatch?.params.sessionId ?? null

  const [sessions, setSessions] = useState<ChatSessionOut[]>([])
  const [sessionFilter, setSessionFilter] = useState('')
  const [historyHidden, setHistoryHidden] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [editTitle, setEditTitle] = useState('')
  const [openMenuId, setOpenMenuId] = useState<number | null>(null)
  const [menuAbove, setMenuAbove] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
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

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

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
      await renameSession(id, trimmed)
    } catch {
      // Silently fail
    }
    setEditingId(null)
    renamingRef.current = false
  }

  const handleDelete = async (id: number) => {
    setOpenMenuId(null)
    try {
      await deleteSession(id)
    } catch {
      // Silently fail
    }
  }

  const openMenu = (id: number, triggerEl: HTMLButtonElement) => {
    const rect = triggerEl.getBoundingClientRect()
    // Open above if less than 120px below the trigger
    setMenuAbove(window.innerHeight - rect.bottom < 120)
    setOpenMenuId(id)
  }

  const renameSession = useCallback(
    async (id: number, title: string) => {
      const updated = await apiClient<ChatSessionOut>(`/chat/sessions/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ title }),
      })
      setSessions((prev) => prev.map((s) => (s.id === id ? updated : s)))
    },
    [apiClient],
  )

  const deleteSession = useCallback(
    async (id: number) => {
      await apiClient(`/chat/sessions/${id}`, { method: 'DELETE' })
      setSessions((prev) => prev.filter((s) => s.id !== id))
      if (activeSessionId === String(id)) navigate('/chat', { replace: true })
    },
    [apiClient, activeSessionId, navigate],
  )

  const outletContext: ChatOutletContext = {
    refreshSessions: fetchSessions,
    sessions,
    renameSession,
    deleteSession,
  }

  // Close menu on outside click
  useEffect(() => {
    if (openMenuId === null) return
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [openMenuId])

  const filterQuery = sessionFilter.trim().toLowerCase()
  const filteredSessions = filterQuery
    ? sessions.filter((s) => (s.title ?? '').toLowerCase().includes(filterQuery))
    : sessions
  const visibleSessions = filteredSessions.slice(0, 20)
  const hasMore = filteredSessions.length > 20

  return (
    <div className="h-screen bg-background text-foreground flex">
      {/* Sidebar */}
      <aside className="w-65 shrink-0 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col h-full">
        {/* Brand + new chat + session search */}
        <div className="px-[var(--spacing-sidebar-x)] pt-5 pb-3 shrink-0">
          <Link to="/chat" className="flex items-center gap-2.5 mb-4">
            <div className="w-7.5 h-7.5 rounded-lg bg-gradient-to-br from-primary/35 to-primary/15 border border-primary/20 flex items-center justify-center text-primary shrink-0">
              <WineIcon size={15} weight="regular" />
            </div>
            <span className="text-base font-medium text-foreground">{t('brand')}</span>
          </Link>

          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="flex items-center gap-2 w-full px-3.5 py-2 rounded-lg border border-border bg-transparent text-[length:var(--text-sidebar)] font-light text-muted-foreground hover:border-border-warm hover:text-sidebar-foreground hover:bg-accent-glow transition-colors mb-2"
          >
            <Plus size={16} weight="regular" className="text-muted-foreground" />
            {t('nav.newChat')}
          </button>

          <div className="relative">
            <MagnifyingGlass
              size={12}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/40 pointer-events-none"
            />
            <input
              type="text"
              value={sessionFilter}
              onChange={(e) => setSessionFilter(e.target.value)}
              placeholder={t('nav.searchHistory')}
              className="w-full px-3.5 py-2 pl-8 rounded-lg border border-border bg-transparent text-[length:var(--text-sidebar)] font-light text-muted-foreground placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/20 transition-colors"
            />
          </div>
        </div>

        <div className="border-t border-sidebar-border mx-[var(--spacing-sidebar-x)]" />

        {/* Navigation */}
        <nav className="shrink-0 px-2 py-2 flex flex-col gap-0.5 border-b border-sidebar-border">
          {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => {
            const active =
              location.pathname === to ||
              (to === '/chats' && /^\/chat\/\d+/.test(location.pathname)) ||
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

        {/* Session history — flex-1, scrollable */}
        <div className="flex-1 overflow-y-auto min-h-0 flex flex-col">
          {/* Recents header */}
          <div className="group/recents flex items-center justify-between px-[var(--spacing-sidebar-x)] pt-2 pb-1 shrink-0">
            <span className="text-[length:var(--text-sidebar-xs)] font-medium text-muted-foreground/40 uppercase tracking-wider">
              {t('nav.recents')}
            </span>
            <button
              type="button"
              onClick={() => setHistoryHidden((v) => !v)}
              className="text-[length:var(--text-sidebar-xs)] text-muted-foreground/40 hover:text-muted-foreground opacity-0 group-hover/recents:opacity-100 transition-opacity"
            >
              {historyHidden ? t('nav.show') : t('nav.hide')}
            </button>
          </div>

          {!historyHidden && visibleSessions.length === 0 && (
            <p className="px-[var(--spacing-sidebar-x)] py-2 text-[length:var(--text-sidebar-xs)] text-muted-foreground/40">
              {filterQuery ? t('nav.noMatch') : t('nav.noConversations')}
            </p>
          )}

          {!historyHidden &&
            visibleSessions.map((session) => {
              const isActive = activeSessionId === String(session.id)
              const menuOpen = openMenuId === session.id
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
                  {editingId === session.id ? (
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
                      <div ref={menuOpen ? menuRef : null} className="relative shrink-0">
                        <button
                          type="button"
                          onClick={(e) => {
                            if (menuOpen) {
                              setOpenMenuId(null)
                            } else {
                              openMenu(session.id, e.currentTarget)
                            }
                          }}
                          className={`flex items-center justify-center w-6 h-6 rounded text-muted-foreground/50 hover:text-foreground hover:bg-white/[0.06] transition-colors ${menuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}
                        >
                          <DotsThree size={16} weight="bold" />
                        </button>
                        {menuOpen && (
                          <div
                            className={`absolute right-0 w-36 rounded-xl bg-popover border border-border shadow-lg py-1 z-50 ${menuAbove ? 'bottom-full mb-1' : 'top-full mt-1'}`}
                          >
                            <button
                              type="button"
                              onClick={() => {
                                setEditTitle(session.title ?? '')
                                setEditingId(session.id)
                                setOpenMenuId(null)
                              }}
                              className="flex items-center gap-2.5 w-full px-3 py-1.5 text-[length:var(--text-sidebar)] text-foreground hover:bg-white/[0.04] transition-colors"
                            >
                              <PencilSimple size={12} className="opacity-50" />
                              {t('nav.rename')}
                            </button>
                            <div className="mx-3 my-1 border-t border-border" />
                            <button
                              type="button"
                              onClick={() => handleDelete(session.id)}
                              className="flex items-center gap-2.5 w-full px-3 py-1.5 text-[length:var(--text-sidebar)] text-destructive hover:bg-white/[0.04] transition-colors"
                            >
                              <Trash size={12} />
                              {t('nav.delete')}
                            </button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
              )
            })}

          {/* All chats link */}
          {!historyHidden && (sessions.length > 0 || hasMore) && (
            <Link
              to="/chats"
              className="flex items-center gap-2 px-[var(--spacing-sidebar-x)] py-2 mt-0.5 text-[length:var(--text-sidebar-xs)] text-muted-foreground/40 hover:text-muted-foreground transition-colors"
            >
              <ChatCircle size={12} className="opacity-60" />
              {t('nav.allChats')}
            </Link>
          )}
        </div>

        {/* Profile footer */}
        <div className="shrink-0 border-t border-sidebar-border px-4 py-3.5">
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
              <div className="text-[length:var(--text-sidebar)] font-medium truncate">
                {user?.first_name}
              </div>
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
      <main className="flex-1 min-w-0 flex flex-col overflow-hidden">
        <Outlet context={outletContext} />
      </main>
    </div>
  )
}

export default AppShell
