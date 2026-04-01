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
    <span className="flex items-center gap-1.5 text-[11px] text-muted-foreground/40">
      <span className="flex items-center gap-0.5">
        {keys.map((k) => (
          <kbd
            key={k}
            className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded border border-border/60 bg-white/[0.04] font-mono text-[10px] text-muted-foreground/50"
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
  const isMac = (
    (navigator.userAgentData as { platform?: string } | undefined)?.platform ?? navigator.platform
  )
    .toUpperCase()
    .includes('MAC')
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
      className="fixed inset-0 z-50 bg-black/75 flex items-start justify-center pt-[20vh]"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="w-[560px] bg-popover border border-border rounded-2xl shadow-2xl overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 border-b border-border">
          <MagnifyingGlass size={15} className="text-muted-foreground/40 shrink-0" />
          <input
            autoFocus
            type="text"
            value={query}
            onChange={(e) => updateQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t('nav.searchHistory')}
            className="flex-1 h-12 bg-transparent text-sm font-light placeholder:text-muted-foreground/40 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 w-6 h-6 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-muted-foreground hover:bg-white/[0.06] transition-colors"
          >
            <X size={13} />
          </button>
        </div>

        {/* Results */}
        <ul ref={listRef} className="max-h-[400px] overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <li className="px-4 py-8 text-center text-[13px] text-muted-foreground/40">
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
                    className={`flex items-center justify-between w-full px-4 py-2.5 text-left transition-colors ${
                      isHighlighted
                        ? 'bg-white/[0.06]'
                        : isActive
                          ? 'bg-accent-glow'
                          : 'hover:bg-white/[0.04]'
                    }`}
                  >
                    <span
                      className={`text-[13px] truncate min-w-0 flex-1 ${isActive ? 'text-primary' : 'text-foreground/80'}`}
                    >
                      {session.title ?? t('nav.untitled')}
                    </span>
                    <span className="font-mono text-[11px] text-muted-foreground/40 shrink-0 ml-3">
                      {timeAgo(session.updated_at, t)}
                    </span>
                  </button>
                </li>
              )
            })
          )}
        </ul>

        {/* Keyboard hints footer */}
        <div className="flex items-center gap-4 px-4 py-2.5 border-t border-border">
          <KbdHint keys={['↑', '↓']} label={t('nav.kbdSelect')} />
          <KbdHint keys={['↵']} label={t('nav.kbdOpen')} />
          <KbdHint keys={[isMac ? '⌘' : 'Ctrl', 'K']} label={t('nav.kbdClose')} />
        </div>
      </div>
    </div>
  )
}

export default ChatSearchModal
