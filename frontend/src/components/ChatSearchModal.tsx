import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MagnifyingGlassIcon as MagnifyingGlass, XIcon as X } from '@phosphor-icons/react'
import type { ChatSessionOut } from '@/lib/types'
import { timeAgo } from '@/lib/utils'

interface ChatSearchModalProps {
  sessions: ChatSessionOut[]
  activeSessionId: string | null
  onNavigate: (id: number) => void
  onClose: () => void
}

function KbdHint({ keys, label }: { keys: string[]; label: string }) {
  return (
    <span className="text-muted-foreground/40 flex items-center gap-1.5 text-[11px]">
      <span className="flex items-center gap-0.5">
        {keys.map((k) => (
          <kbd
            key={k}
            className="border-border/60 text-muted-foreground/50 inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border bg-white/[0.04] px-1 font-mono text-[10px]"
          >
            {k}
          </kbd>
        ))}
      </span>
      {label}
    </span>
  )
}

function ChatSearchModal({ sessions, activeSessionId, onNavigate, onClose }: ChatSearchModalProps) {
  const { t } = useTranslation()
  const isMac = /mac/i.test(navigator.userAgent) && !/iphone|ipad/i.test(navigator.userAgent)
  const [query, setQuery] = useState('')
  const [highlightedIndex, setHighlightedIndex] = useState(0)

  function updateQuery(value: string) {
    setQuery(value)
    setHighlightedIndex(0)
  }
  const listRef = useRef<HTMLUListElement>(null)

  const trimmed = query.trim().toLowerCase()
  const filtered = trimmed
    ? sessions.filter((s) => (s.title ?? '').toLowerCase().includes(trimmed))
    : sessions.slice(0, 20)

  // Scroll highlighted row into view
  useEffect(() => {
    const item = listRef.current?.children[highlightedIndex] as HTMLElement | undefined
    item?.scrollIntoView({ block: 'nearest' })
  }, [highlightedIndex])

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlightedIndex((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightedIndex((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && filtered[highlightedIndex]) {
      onNavigate(filtered[highlightedIndex].id)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/75 pt-[20vh]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="bg-popover border-border w-[560px] overflow-hidden rounded-2xl border shadow-2xl">
        {/* Search input */}
        <div className="border-border flex items-center gap-3 border-b px-4">
          <MagnifyingGlass size={15} className="text-muted-foreground/40 shrink-0" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => updateQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('nav.searchHistory')}
            className="placeholder:text-muted-foreground/40 h-12 flex-1 bg-transparent text-sm font-light focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground/40 hover:text-muted-foreground flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors hover:bg-white/[0.06]"
          >
            <X size={13} />
          </button>
        </div>

        {/* Results */}
        <ul ref={listRef} className="max-h-[400px] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <li className="text-muted-foreground/40 px-4 py-8 text-center text-[13px]">
              {t('nav.noMatch')}
            </li>
          ) : (
            filtered.map((session, i) => {
              const isActive = activeSessionId === String(session.id)
              const isHighlighted = i === highlightedIndex
              return (
                <li key={session.id}>
                  <button
                    type="button"
                    onMouseEnter={() => setHighlightedIndex(i)}
                    onClick={() => onNavigate(session.id)}
                    className={`flex w-full items-center justify-between px-4 py-2.5 text-left transition-colors ${
                      isHighlighted
                        ? 'bg-white/[0.06]'
                        : isActive
                          ? 'bg-accent-glow'
                          : 'hover:bg-white/[0.04]'
                    }`}
                  >
                    <span
                      className={`min-w-0 flex-1 truncate text-[13px] ${isActive ? 'text-primary' : 'text-foreground/80'}`}
                    >
                      {session.title ?? t('nav.untitled')}
                    </span>
                    <span className="text-muted-foreground/40 ml-3 shrink-0 font-mono text-[11px]">
                      {timeAgo(session.updated_at, t)}
                    </span>
                  </button>
                </li>
              )
            })
          )}
        </ul>

        {/* Keyboard hints footer */}
        <div className="border-border flex items-center gap-4 border-t px-4 py-2.5">
          <KbdHint keys={['↑', '↓']} label={t('nav.kbdSelect')} />
          <KbdHint keys={['↵']} label={t('nav.kbdOpen')} />
          <KbdHint keys={[isMac ? '⌘' : 'Ctrl', 'K']} label={t('nav.kbdClose')} />
        </div>
      </div>
    </div>
  )
}

export default ChatSearchModal
