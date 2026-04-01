import { useState, useMemo } from 'react'
import { useNavigate, useOutletContext } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  MagnifyingGlassIcon as MagnifyingGlass,
  ChatCircleIcon as ChatCircle,
  XIcon as X,
  TrashIcon as Trash,
} from '@phosphor-icons/react'
import type { ChatOutletContext } from '@/components/AppShell'
import EmptyState from '@/components/EmptyState'
import { timeAgo } from '@/lib/utils'

function ChatsPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { sessions, deleteSession } = useOutletContext<ChatOutletContext>()

  const [query, setQuery] = useState('')
  const [selecting, setSelecting] = useState(false)
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [confirmBulk, setConfirmBulk] = useState(false)
  const [deleting, setDeleting] = useState(false)

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? sessions.filter((s) => (s.title ?? '').toLowerCase().includes(q)) : sessions
  }, [sessions, query])

  const allSelected = filtered.length > 0 && filtered.every((s) => selected.has(s.id))

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
    for (const id of [...selected]) {
      try {
        await deleteSession(id)
      } catch {
        // continue with remaining
      }
    }
    setSelected(new Set())
    setConfirmBulk(false)
    setDeleting(false)
    setSelecting(false)
  }

  const selectedCount = selected.size

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-baseline justify-between mb-6">
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-2xl font-light">{t('nav.chat')}</h1>
            {sessions.length > 0 && (
              <span className="font-mono text-[11px] text-muted-foreground/60 tabular-nums">
                {sessions.length}
              </span>
            )}
          </div>

          {sessions.length > 0 && !selecting && (
            <button
              type="button"
              onClick={() => setSelecting(true)}
              className="text-[13px] text-muted-foreground/60 hover:text-foreground transition-colors"
            >
              {t('chats.select')}
            </button>
          )}

          {selecting && !confirmBulk && (
            <div className="flex items-center gap-3">
              {selectedCount > 0 && (
                <button
                  type="button"
                  onClick={() => setConfirmBulk(true)}
                  className="flex items-center gap-1.5 text-[13px] text-destructive hover:text-destructive/80 transition-colors"
                >
                  <Trash size={13} />
                  {t('chats.deleteSelected', { count: selectedCount })}
                </button>
              )}
              <button
                type="button"
                onClick={exitSelectMode}
                className="text-[13px] text-muted-foreground/60 hover:text-foreground transition-colors"
              >
                {t('chats.cancel')}
              </button>
            </div>
          )}

          {confirmBulk && (
            <div className="flex items-center gap-3 text-[13px]">
              <span className="text-muted-foreground">
                {t('chats.deleteConfirm', { count: selectedCount })}
              </span>
              <button
                type="button"
                onClick={handleBulkDelete}
                disabled={deleting}
                className="text-destructive hover:text-destructive/80 disabled:opacity-50 transition-colors"
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
        </div>

        {sessions.length === 0 ? (
          <EmptyState
            icon={<ChatCircle size={28} />}
            title={t('nav.noConversations')}
            description={t('chats.emptyDesc')}
            cta={{ label: t('nav.newChat'), onClick: () => navigate('/chat') }}
          />
        ) : (
          <>
            {/* Search */}
            <div className="relative mb-5">
              <MagnifyingGlass
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
              />
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={t('nav.searchHistory')}
                className="w-full h-9 pl-8 pr-3 rounded-lg bg-white/[0.04] border border-border text-[13px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors"
              />
            </div>

            {selecting && (
              <div className="flex items-center gap-2 mb-3">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="accent-primary"
                />
                <span className="text-[12px] text-muted-foreground/60">
                  {selectedCount > 0
                    ? t('chats.selectedCount', { count: selectedCount })
                    : t('chats.selectAll')}
                </span>
              </div>
            )}

            {filtered.length === 0 ? (
              <EmptyState icon={<MagnifyingGlass size={28} />} title={t('nav.noMatch')} />
            ) : (
              <ul className="flex flex-col">
                {filtered.map((session) => (
                  <li
                    key={session.id}
                    className="group flex items-center gap-2.5 py-3 border-b border-border hover:bg-surface-hover -mx-2 px-2 rounded-lg transition-colors"
                  >
                    {selecting && (
                      <input
                        type="checkbox"
                        checked={selected.has(session.id)}
                        onChange={() => toggle(session.id)}
                        className="accent-primary shrink-0"
                      />
                    )}

                    <button
                      type="button"
                      onClick={() => navigate(`/chat/${session.id}`)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <p className="text-[14px] font-medium leading-snug truncate">
                        {session.title ?? t('nav.untitled')}
                      </p>
                      <p className="text-[11px] text-muted-foreground/60 font-mono mt-0.5">
                        {timeAgo(session.updated_at, t)}
                      </p>
                    </button>

                    {!selecting && (
                      <button
                        type="button"
                        onClick={() => deleteSession(session.id)}
                        className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors opacity-0 group-hover:opacity-100"
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
