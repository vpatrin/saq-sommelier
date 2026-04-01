import { WineDetailProvider, useWineDetail } from '@/contexts/WineDetailContext'
import WineDetailPanel from '@/components/WineDetailPanel'
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
  WineIcon,
  SidebarSimpleIcon,
  CaretUpIcon as CaretUp,
  NotePencilIcon as NotePencil,
  ChartDonutIcon as ChartDonut,
} from '@phosphor-icons/react'
import type { ChatSessionOut } from '@/lib/types'
import UserMenu from '@/components/UserMenu'

const NAV_ITEMS = [
  { to: '/chats', labelKey: 'nav.chat', icon: ChatCircle },
  { to: '/search', labelKey: 'nav.search', icon: MagnifyingGlass },
  { to: '/watches', labelKey: 'nav.myWatches', icon: Eye },
  { to: '/stores', labelKey: 'nav.myStores', icon: MapPin },
] as const

const SOON_ITEMS = [
  { labelKey: 'nav.journal', icon: NotePencil },
  { labelKey: 'nav.cellar', icon: ChartDonut },
] as const

export interface ChatOutletContext {
  refreshSessions: () => void
  sessions: ChatSessionOut[]
  renameSession: (id: number, title: string) => Promise<void>
  deleteSession: (id: number) => Promise<void>
}

function getInitialCollapsed(): boolean {
  try {
    return localStorage.getItem('sidebar:collapsed') === 'true'
  } catch {
    return false
  }
}

function AppShell() {
  const { t, i18n } = useTranslation()
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const apiClient = useApiClient()

  const sessionMatch = useMatch('/chat/:sessionId')
  const activeSessionId = sessionMatch?.params.sessionId ?? null

  const [collapsed, setCollapsed] = useState(getInitialCollapsed)
  const [userMenuOpen, setUserMenuOpen] = useState(false)

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

  const toggleCollapsed = useCallback(() => {
    setCollapsed((v) => {
      const next = !v
      try {
        localStorage.setItem('sidebar:collapsed', String(next))
      } catch {
        // localStorage unavailable (private mode) — collapse state won't persist
      }
      return next
    })
    setUserMenuOpen(false)
  }, [])

  const fetchSessions = useCallback(async () => {
    try {
      const data = await apiClient<ChatSessionOut[]>('/chat/sessions')
      setSessions(data)
    } catch {
      // Silently fail — sidebar is non-critical
    }
  }, [apiClient])

  useEffect(() => {
    let cancelled = false
    apiClient<ChatSessionOut[]>('/chat/sessions')
      .then((data) => {
        if (!cancelled) setSessions(data)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [apiClient])

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

  const userMenuRef = useRef<HTMLDivElement>(null)

  // Close user menu on outside click (excluding the trigger button)
  useEffect(() => {
    if (!userMenuOpen) return
    const handler = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [userMenuOpen])

  // Close session menu on outside click
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

  const isNavActive = useCallback(
    (to: string) =>
      location.pathname === to ||
      (to === '/chats' && /^\/chat\/\d+/.test(location.pathname)) ||
      (to === '/stores' && location.pathname === '/stores/nearby'),
    [location.pathname],
  )

  return (
    <div className="h-screen bg-background text-foreground flex">
      {/* Sidebar */}
      <aside
        className={`shrink-0 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col h-full transition-[width] duration-300 ease-out ${
          collapsed ? 'w-[60px] overflow-visible' : 'w-65 overflow-hidden'
        }`}
      >
        {collapsed ? (
          <div className="flex flex-col items-center py-4 gap-1 h-full">
            <Link
              to="/chat"
              className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary/35 to-primary/15 border border-primary/20 flex items-center justify-center text-primary shrink-0 mb-2"
            >
              <WineIcon size={15} weight="regular" />
            </Link>

            <button
              type="button"
              onClick={toggleCollapsed}
              title={t('nav.expandSidebar')}
              className="w-[38px] h-[38px] rounded-lg flex items-center justify-center text-muted-foreground/40 hover:text-muted-foreground hover:bg-surface-hover transition-colors mb-1"
            >
              <SidebarSimpleIcon size={17} />
            </button>

            <div className="w-6 h-px bg-border my-1" />

            <button
              type="button"
              onClick={() => navigate('/chat')}
              title={t('nav.newChat')}
              className="w-[38px] h-[38px] rounded-lg flex items-center justify-center text-muted-foreground/40 hover:text-muted-foreground hover:bg-surface-hover transition-colors"
            >
              <Plus size={18} />
            </button>

            <div className="w-6 h-px bg-border my-1" />

            {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => {
              const active = isNavActive(to)
              return (
                <Link
                  key={to}
                  to={to}
                  title={t(labelKey)}
                  className={`w-[38px] h-[38px] rounded-lg flex items-center justify-center transition-colors ${
                    active
                      ? 'bg-accent-glow text-primary'
                      : 'text-muted-foreground/40 hover:text-muted-foreground hover:bg-surface-hover'
                  }`}
                >
                  <Icon size={17} weight={active ? 'fill' : 'regular'} />
                </Link>
              )
            })}

            {SOON_ITEMS.map(({ labelKey, icon: Icon }) => (
              <div
                key={labelKey}
                title={`${t(labelKey)} — ${t('userMenu.soon')}`}
                className="w-[38px] h-[38px] rounded-lg flex items-center justify-center text-muted-foreground/20 cursor-not-allowed"
              >
                <Icon size={17} />
              </div>
            ))}

            <div ref={userMenuRef} className="mt-auto relative overflow-visible">
              <button
                type="button"
                onClick={() => setUserMenuOpen((v) => !v)}
                title={user?.first_name}
                className="w-8 h-8 rounded-full bg-primary/15 border border-primary/20 flex items-center justify-center text-[13px] font-medium text-primary hover:opacity-80 transition-opacity"
              >
                {user?.first_name?.charAt(0) ?? '?'}
              </button>
              {userMenuOpen && (
                <UserMenu
                  firstName={user?.first_name ?? ''}
                  onLogout={handleLogout}
                  currentLanguage={i18n.resolvedLanguage ?? 'fr'}
                  onLanguageChange={(lang) => i18n.changeLanguage(lang)}
                  placement="right"
                />
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="px-[var(--spacing-sidebar-x)] pt-5 pb-3 shrink-0">
              <div className="flex items-center justify-between mb-4">
                <Link to="/chat" className="flex items-center gap-2.5">
                  <div className="w-7.5 h-7.5 rounded-lg bg-gradient-to-br from-primary/35 to-primary/15 border border-primary/20 flex items-center justify-center text-primary shrink-0">
                    <WineIcon size={15} weight="regular" />
                  </div>
                  <span className="text-base font-medium text-foreground">{t('brand')}</span>
                </Link>
                <button
                  type="button"
                  onClick={toggleCollapsed}
                  title={t('nav.collapseSidebar')}
                  className="w-7 h-7 rounded-lg flex items-center justify-center text-muted-foreground/30 hover:text-muted-foreground hover:bg-surface-hover transition-colors"
                >
                  <SidebarSimpleIcon size={15} />
                </button>
              </div>

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

            <nav className="shrink-0 px-2 py-2 flex flex-col gap-0.5 border-b border-sidebar-border">
              {NAV_ITEMS.map(({ to, labelKey, icon: Icon }) => {
                const active = isNavActive(to)
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
              {SOON_ITEMS.map(({ labelKey, icon: Icon }) => (
                <div
                  key={labelKey}
                  className="flex items-center gap-2.5 px-3 py-2 text-[length:var(--text-sidebar)] rounded-lg text-muted-foreground/25 cursor-not-allowed"
                >
                  <Icon size={16} className="opacity-70" />
                  {t(labelKey)}
                  <span className="ml-auto font-mono text-[9px] px-1.5 py-0.5 rounded border border-primary/15 bg-primary/[0.06] text-primary/40">
                    {t('userMenu.soon')}
                  </span>
                </div>
              ))}
            </nav>

            <div className="flex-1 overflow-y-auto min-h-0 flex flex-col">
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
                                className={`absolute right-0 w-40 rounded-xl bg-popover border border-border shadow-lg py-1 z-50 ${menuAbove ? 'bottom-full mb-1' : 'top-full mt-1'}`}
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
                                  className="flex items-center gap-2.5 w-full px-3 py-1.5 text-[length:var(--text-sidebar)] text-destructive hover:bg-white/[0.04] transition-colors whitespace-nowrap"
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

            <div
              ref={userMenuRef}
              className="shrink-0 border-t border-sidebar-border px-3 py-3 relative"
            >
              {userMenuOpen && (
                <UserMenu
                  firstName={user?.first_name ?? ''}
                  onLogout={handleLogout}
                  currentLanguage={i18n.resolvedLanguage ?? 'fr'}
                  onLanguageChange={(lang) => i18n.changeLanguage(lang)}
                />
              )}
              <button
                type="button"
                onClick={() => setUserMenuOpen((v) => !v)}
                className="flex items-center gap-2.5 w-full rounded-lg px-2 py-2 hover:bg-surface-hover transition-colors"
              >
                <div className="w-8 h-8 rounded-full bg-primary/15 border border-primary/20 flex items-center justify-center text-[length:var(--text-sidebar)] font-medium text-primary shrink-0">
                  {user?.first_name?.charAt(0) ?? '?'}
                </div>
                <div className="flex-1 min-w-0 text-left">
                  <p className="text-[13px] font-medium truncate">{user?.first_name}</p>
                  <p className="text-[10px] text-muted-foreground/40">
                    {t('userMenu.connectedViaTelegram')}
                  </p>
                </div>
                <CaretUp
                  size={12}
                  className={`text-muted-foreground/40 transition-transform ${userMenuOpen ? '' : 'rotate-180'}`}
                />
              </button>
            </div>
          </>
        )}
      </aside>

      <MainArea outletContext={outletContext} />
    </div>
  )
}

function MainArea({ outletContext }: { outletContext: ChatOutletContext }) {
  const location = useLocation()
  const { selectedSku, setSelectedSku } = useWineDetail()
  const handleClosePanel = useCallback(() => setSelectedSku(null), [setSelectedSku])

  // Close panel on navigation
  useEffect(() => {
    setSelectedSku(null)
  }, [location.pathname, setSelectedSku])

  return (
    <main className="flex-1 min-w-0 flex flex-col overflow-hidden relative">
      <Outlet context={outletContext} />
      <WineDetailPanel sku={selectedSku} onClose={handleClosePanel} />
    </main>
  )
}

function AppShellWithProvider() {
  return (
    <WineDetailProvider>
      <AppShell />
    </WineDetailProvider>
  )
}

export default AppShellWithProvider
