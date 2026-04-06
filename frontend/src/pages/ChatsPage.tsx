import { useState, useMemo, useEffect, useCallback } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  MagnifyingGlassIcon as MagnifyingGlass,
  ChatCircleIcon as ChatCircle,
  PlusIcon as Plus,
  TrashIcon as Trash,
  XIcon as X,
} from '@phosphor-icons/react'
import type { ChatOutletContext } from '@/components/AppShell'
import type { ChatSessionOut } from '@/lib/types'
import { useApiClient, fetchAllPages } from '@/lib/api'
import EmptyState from '@/components/EmptyState'
import { timeAgoPrecise } from '@/lib/utils'

function ChatsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { deleteSession } = useOutletContext<ChatOutletContext>()
  const apiClient = useApiClient()

  const [allSessions, setAllSessions] = useState<ChatSessionOut[]>([])
  const [loadError, setLoadError] = useState(false)

  const loadAll = useCallback(
    () =>
      fetchAllPages<ChatSessionOut>('/chat/sessions', apiClient)
        .then((data) => setAllSessions(data))
        .catch(() => setLoadError(true)),
    [apiClient],
  )

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const [query, setQuery] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [confirmBulk, setConfirmBulk] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? allSessions.filter((s) => (s.title ?? '').toLowerCase().includes(q)) : allSessions
  }, [allSessions, query])

  const allSelected = filtered.length > 0 && filtered.every((s) => selected.has(s.id))
  const selectedCount = selected.size

  function toggleAll() {
    if (allSelected) {
      setSelected((prev) => {
        const next = new Set(prev)
        filtered.forEach((s) => next.delete(s.id))
        return next
      })
    } else {
      setSelected((prev) => {
        const next = new Set(prev)
        filtered.forEach((s) => next.add(s.id))
        return next
      })
    }
  }

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function exitSelectMode() {
    setSelecting(false)
    setSelected(new Set())
    setConfirmBulk(false)
  }

  async function handleBulkDelete() {
    setDeleting(true)
    const ids = [...selected]
    for (const id of ids) {
      try {
        await deleteSession(id)
      } catch {
        // continue with remaining
      }
    }
    setAllSessions((prev) => prev.filter((s) => !ids.includes(s.id)))
    setSelected(new Set())
    setConfirmBulk(false)
    setDeleting(false)
    setSelecting(false)
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-2xl font-light">{t('nav.chat')}</h1>
            {allSessions.length > 0 && (
              <span className="text-muted-foreground/60 font-mono text-[11px] tabular-nums">
                {allSessions.length}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={() => navigate('/chat')}
            className="border-border text-muted-foreground hover:text-foreground hover:border-border/80 flex h-9 w-9 items-center justify-center rounded-xl border bg-white/[0.04] transition-colors hover:bg-white/[0.08]"
            aria-label={t('nav.newChat')}
          >
            <Plus size={16} />
          </button>
        </div>

        {loadError ? (
          <p className="text-muted-foreground/60 text-[13px]">
            {t('chat.failedToLoad')} —{' '}
            <button
              type="button"
              onClick={() => {
                setLoadError(false)
                loadAll().catch(() => setLoadError(true))
              }}
              className="hover:text-foreground underline transition-colors"
            >
              {t('chat.retry')}
            </button>
          </p>
        ) : allSessions.length === 0 ? (
          <EmptyState
            icon={<ChatCircle size={28} />}
            title={t('nav.noConversations')}
            description={t('chats.emptyDesc')}
            cta={{ label: t('nav.newChat'), onClick: () => navigate('/chat') }}
          />
        ) : (
          <>
            {/* Search */}
            <div className="relative mb-4">
              <MagnifyingGlass
                size={14}
                className="text-muted-foreground/50 pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('nav.searchHistory')}
                className="border-border placeholder:text-muted-foreground/40 focus:border-primary/30 h-9 w-full rounded-lg border bg-white/[0.04] pr-3 pl-8 text-[13px] transition-colors focus:outline-none"
              />
            </div>

            {/* Subheader row */}
            {!selecting && (
              <div className="mb-3 flex items-center justify-between">
                <span className="text-muted-foreground/40 text-[12px]">{t('chats.yourChats')}</span>
                <button
                  type="button"
                  onClick={() => setSelecting(true)}
                  className="text-primary/70 hover:text-primary text-[12px] transition-colors"
                >
                  {t('chats.select')}
                </button>
              </div>
            )}

            {/* Select toolbar — shown when selecting */}
            {selecting && (
              <div className="border-border mb-3 flex items-center gap-3 rounded-lg border bg-white/[0.03] px-2 py-2">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="accent-primary shrink-0"
                />
                <span className="text-muted-foreground/70 flex-1 text-[13px]">
                  {selectedCount > 0
                    ? t('chats.selectedCount', { count: selectedCount })
                    : t('chats.selectAll')}
                </span>
                {selectedCount > 0 && !confirmBulk && (
                  <button
                    type="button"
                    onClick={() => setConfirmBulk(true)}
                    className="text-muted-foreground/50 hover:text-destructive hover:bg-destructive/10 flex h-7 w-7 items-center justify-center rounded-md transition-colors"
                    aria-label={t('chats.deleteSelected', { count: selectedCount })}
                  >
                    <Trash size={14} />
                  </button>
                )}
                {confirmBulk && (
                  <div className="flex items-center gap-2 text-[12px]">
                    <span className="text-muted-foreground/60">
                      {t('chats.deleteConfirm', { count: selectedCount })}
                    </span>
                    <button
                      type="button"
                      onClick={handleBulkDelete}
                      disabled={deleting}
                      className="text-destructive hover:text-destructive/80 transition-colors disabled:opacity-50"
                    >
                      {deleting ? t('chats.deleting') : t('nav.yes')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmBulk(false)}
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {t('nav.no')}
                    </button>
                  </div>
                )}
                <button
                  type="button"
                  onClick={exitSelectMode}
                  className="text-muted-foreground/40 hover:text-foreground flex h-7 w-7 items-center justify-center rounded-md transition-colors hover:bg-white/[0.06]"
                  aria-label={t('chats.cancel')}
                >
                  <X size={14} />
                </button>
              </div>
            )}

            {filtered.length === 0 ? (
              <EmptyState icon={<MagnifyingGlass size={28} />} title={t('nav.noMatch')} />
            ) : (
              <ul className="flex flex-col">
                {filtered.map((session) => (
                  <li
                    key={session.id}
                    className="group border-border hover:bg-surface-hover -mx-2 flex items-center gap-2.5 rounded-lg border-b px-2 py-3 transition-colors"
                  >
                    {selecting && (
                      <input
                        type="checkbox"
                        checked={selected.has(session.id)}
                        onChange={() => toggle(session.id)}
                        onClick={(e) => e.stopPropagation()}
                        className="accent-primary shrink-0 cursor-pointer"
                      />
                    )}

                    <button
                      type="button"
                      onClick={() =>
                        selecting ? toggle(session.id) : navigate(`/chat/${session.id}`)
                      }
                      className="min-w-0 flex-1 text-left"
                    >
                      <p className="truncate text-[14px] leading-snug font-medium">
                        {session.title ?? t('nav.untitled')}
                      </p>
                      <p className="text-muted-foreground/60 mt-0.5 text-[11px] font-light">
                        {timeAgoPrecise(session.updated_at, t)}
                      </p>
                    </button>

                    {!selecting && (
                      <button
                        type="button"
                        onClick={async () => {
                          await deleteSession(session.id)
                          setAllSessions((prev) => prev.filter((s) => s.id !== session.id))
                        }}
                        className="text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 flex h-6 w-6 shrink-0 items-center justify-center rounded-md opacity-0 transition-colors group-hover:opacity-100"
                        aria-label={t('nav.deleteSession')}
                      >
                        <X size={13} weight="bold" />
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default ChatsPage
