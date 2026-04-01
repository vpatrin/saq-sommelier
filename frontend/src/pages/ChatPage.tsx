import { useState, useRef, useEffect, useCallback, useMemo, lazy, Suspense } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router'
import { useTranslation } from 'react-i18next'

const ReactMarkdown = lazy(() => import('react-markdown'))
import {
  ArrowClockwiseIcon as ArrowClockwise,
  ArrowDownIcon as ArrowDown,
  ArrowUpIcon as ArrowUp,
  CaretDownIcon as CaretDown,
  CheckIcon as Check,
  CopyIcon as Copy,
  PencilSimpleIcon as PencilSimple,
  ThumbsDownIcon as ThumbsDown,
  ThumbsUpIcon as ThumbsUp,
  TrashIcon as Trash,
  WineIcon as Wine,
} from '@phosphor-icons/react'
import { useApiClient } from '@/lib/api'
import type { ChatOutletContext } from '@/components/AppShell'
import WineCard from '@/components/WineCard'
import { useWineDetail } from '@/contexts/WineDetailContext'
import type {
  ChatSessionOut,
  ChatMessageOut,
  ChatSessionDetailOut,
  RecommendationOut,
  UserStorePreferenceOut,
} from '@/lib/types'

const MAX_MESSAGE_LENGTH = 2000

function isRecommendation(content: string | RecommendationOut): content is RecommendationOut {
  return typeof content === 'object' && 'products' in content
}

const THINKING_STEPS = [
  'intent_route: analyzing…',
  'sql_filter: scanning catalog…',
  'pgvector: semantic search…',
  'mmr_rerank: diversifying…',
  'claude: curating…',
]

function ThinkingIndicator() {
  const [step, setStep] = useState(0)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>
    const id = setInterval(() => {
      setVisible(false)
      timeoutId = setTimeout(() => {
        setStep((s) => (s + 1) % THINKING_STEPS.length)
        setVisible(true)
      }, 200)
    }, 1400)
    return () => {
      clearInterval(id)
      clearTimeout(timeoutId)
    }
  }, [])

  return (
    <div className="flex items-center gap-2 px-4 py-3">
      <span className="flex gap-1 items-center shrink-0">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-primary/40 animate-typing-dot"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </span>
      <span
        className="font-mono text-[10.5px] text-muted-foreground/60 transition-opacity duration-200"
        style={{ opacity: visible ? 1 : 0 }}
      >
        {THINKING_STEPS[step]}
      </span>
    </div>
  )
}

function ActionBtn({
  onClick,
  title,
  active,
  activeClass,
  children,
}: {
  onClick: () => void
  title: string
  active?: boolean
  activeClass?: string
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`p-1.5 rounded-md transition-colors hover:bg-white/[0.05] ${active ? (activeClass ?? 'text-primary/80') : 'text-muted-foreground/35 hover:text-muted-foreground/70'}`}
    >
      {children}
    </button>
  )
}

// Actions shown below assistant messages
function AssistantMessageActions({
  content,
  alwaysVisible,
  onRegenerate,
}: {
  content: string | RecommendationOut
  alwaysVisible: boolean
  onRegenerate?: () => void
}) {
  const [thumbState, setThumbState] = useState<'up' | 'down' | null>(null)
  const [copied, setCopied] = useState(false)

  const copyText = useMemo(
    () =>
      typeof content === 'string'
        ? content
        : `${content.summary}\n\n${content.products.map((p) => `${p.product.name} — ${p.reason ?? ''}`).join('\n')}`,
    [content],
  )

  const handleCopy = () => {
    navigator.clipboard.writeText(copyText).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <div
      className={`flex items-center gap-0.5 mt-1.5 ml-0.5 transition-opacity ${alwaysVisible ? 'opacity-100' : 'opacity-0 group-hover/msg:opacity-100'}`}
    >
      <ActionBtn onClick={handleCopy} title="Copy">
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </ActionBtn>
      <ActionBtn
        onClick={() => setThumbState(thumbState === 'up' ? null : 'up')}
        title="Good response"
        active={thumbState === 'up'}
      >
        <ThumbsUp size={13} weight={thumbState === 'up' ? 'fill' : 'regular'} />
      </ActionBtn>
      <ActionBtn
        onClick={() => setThumbState(thumbState === 'down' ? null : 'down')}
        title="Bad response"
        active={thumbState === 'down'}
        activeClass="text-destructive/70"
      >
        <ThumbsDown size={13} weight={thumbState === 'down' ? 'fill' : 'regular'} />
      </ActionBtn>
      {onRegenerate && (
        <ActionBtn onClick={onRegenerate} title="Regenerate">
          <ArrowClockwise size={13} />
        </ActionBtn>
      )}
    </div>
  )
}

// Actions shown to the right of user messages on hover
function UserMessageActions({
  text,
  createdAt,
  onRegenerate,
}: {
  text: string
  createdAt: string
  onRegenerate?: () => void
}) {
  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    })
  }

  const time = useMemo(
    () => new Date(createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    [createdAt],
  )

  return (
    <div className="flex items-center gap-0.5 opacity-0 group-hover/msg:opacity-100 transition-opacity mt-1 self-end">
      <span className="font-mono text-[10px] text-muted-foreground/30 mr-1">{time}</span>
      {onRegenerate && (
        <ActionBtn onClick={onRegenerate} title="Regenerate from here">
          <ArrowClockwise size={13} />
        </ActionBtn>
      )}
      <ActionBtn onClick={handleCopy} title="Copy">
        {copied ? <Check size={13} /> : <Copy size={13} />}
      </ActionBtn>
    </div>
  )
}

function AssistantMessage({
  content,
  storeNames,
  selectedSku,
  setSelectedSku,
}: {
  content: string | RecommendationOut
  storeNames: Map<string, string>
  selectedSku: string | null
  setSelectedSku: (sku: string | null) => void
}) {
  const proseClass =
    'prose prose-sm prose-invert max-w-none text-foreground/80 font-light [&_p]:leading-relaxed [&_ul]:mt-1 [&_ol]:mt-1 [&_li]:my-0.5 [&_strong]:text-foreground [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm'

  if (!isRecommendation(content)) {
    return (
      <Suspense>
        <div className={proseClass}>
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>
      </Suspense>
    )
  }

  return (
    <Suspense>
      <div className="flex flex-col gap-3">
        <div className={proseClass}>
          <ReactMarkdown>{content.summary}</ReactMarkdown>
        </div>
        <div
          className="grid gap-2.5"
          style={{
            gridTemplateColumns: content.products.length > 1 ? 'repeat(2, minmax(0, 1fr))' : '1fr',
          }}
        >
          {content.products.map(({ product, reason }) => (
            <button
              key={product.sku}
              type="button"
              onClick={() => setSelectedSku(selectedSku === product.sku ? null : product.sku)}
              className={`text-left w-full rounded-xl ${selectedSku === product.sku ? 'ring-1 ring-primary/60' : ''}`}
            >
              <WineCard product={product} reason={reason} storeNames={storeNames} />
            </button>
          ))}
        </div>
      </div>
    </Suspense>
  )
}

function SessionTitleBar({
  title,
  onRename,
  onDelete,
}: {
  title: string
  onRename: (title: string) => Promise<void>
  onDelete: () => Promise<void>
}) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [renaming, setRenaming] = useState(false)
  const [draft, setDraft] = useState(title)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const submitRename = async () => {
    const trimmed = draft.trim()
    if (trimmed && trimmed !== title) await onRename(trimmed)
    setRenaming(false)
  }

  const startRenaming = () => {
    setDraft(title)
    setOpen(false)
    setRenaming(true)
  }

  return (
    <div ref={containerRef} className="relative">
      {renaming ? (
        <input
          autoFocus
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') submitRename()
            if (e.key === 'Escape') setRenaming(false)
          }}
          onBlur={submitRename}
          className="h-8 px-3 rounded-lg bg-secondary border border-border text-sm text-foreground focus:outline-none focus:border-primary/40 w-64 text-center"
        />
      ) : (
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          className="flex items-center gap-1.5 h-8 px-3 rounded-lg bg-secondary/60 hover:bg-secondary border border-transparent hover:border-border text-sm text-foreground/70 hover:text-foreground transition-colors max-w-80"
        >
          <span className="truncate">{title}</span>
          <CaretDown size={13} className="shrink-0 opacity-50" />
        </button>
      )}

      {open && (
        <div className="absolute top-full left-0 mt-1.5 w-44 rounded-xl bg-popover border border-border shadow-lg py-1 z-20">
          <button
            type="button"
            className="flex items-center gap-2.5 w-full px-3.5 py-2 text-sm text-foreground hover:bg-white/[0.04] transition-colors"
            onClick={startRenaming}
          >
            <PencilSimple size={13} className="opacity-50" />
            {t('nav.rename')}
          </button>
          <div className="mx-3 my-1 border-t border-border" />
          <button
            type="button"
            className="flex items-center gap-2.5 w-full px-3.5 py-2 text-sm text-destructive hover:bg-white/[0.04] transition-colors"
            onClick={() => {
              setOpen(false)
              onDelete()
            }}
          >
            <Trash size={13} />
            {t('nav.deleteSession')}
          </button>
        </div>
      )}
    </div>
  )
}

function ChatPage() {
  const { t } = useTranslation()
  const apiClient = useApiClient()
  const navigate = useNavigate()
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>()
  const { selectedSku, setSelectedSku } = useWineDetail()
  const { refreshSessions, sessions, renameSession, deleteSession } =
    useOutletContext<ChatOutletContext>()

  // Derive sessionId directly from URL — no intermediate state to get stale
  const sessionId = urlSessionId ? Number(urlSessionId) : null
  const sessionTitle = sessionId ? (sessions.find((s) => s.id === sessionId)?.title ?? null) : null

  const [messages, setMessages] = useState<ChatMessageOut[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFailedInput, setLastFailedInput] = useState<string | null>(null)
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const { lastAssistantIdx, lastUserIdx, lastUserMsg } = useMemo(() => {
    let lastAssistantIdx = -1
    let lastUserIdx = -1
    let lastUserMsg: string | null = null
    messages.forEach((msg, i) => {
      if (msg.role === 'assistant') lastAssistantIdx = i
      else if (msg.role === 'user') {
        lastUserIdx = i
        lastUserMsg = msg.content as string
      }
    })
    return { lastAssistantIdx, lastUserIdx, lastUserMsg }
  }, [messages])

  const [atBottom, setAtBottom] = useState(true)
  const bottomRef = useRef<HTMLDivElement>(null)
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const skipLoadRef = useRef(false)

  // Fetch user's saved stores once (for availability display on wine cards)
  useEffect(() => {
    let cancelled = false
    apiClient<UserStorePreferenceOut[]>('/stores/preferences')
      .then((prefs) => {
        if (!cancelled) setStoreNames(new Map(prefs.map((p) => [p.saq_store_id, p.store.name])))
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [apiClient])

  // Reset transient state when URL changes (new chat vs resume).
  // Skip when skipLoadRef is set — that means submitMessage just created the session
  // and already has the optimistic message in place; clearing would wipe it.
  useEffect(() => {
    if (skipLoadRef.current) return
    setMessages([])
    setInput('')
    setError(null)
    setLastFailedInput(null)
  }, [urlSessionId])

  // Load existing session messages (skipped when submitMessage already has data)
  useEffect(() => {
    if (!sessionId) return
    if (skipLoadRef.current) {
      skipLoadRef.current = false
      return
    }
    let cancelled = false
    setLoading(true)
    apiClient<ChatSessionDetailOut>(`/chat/sessions/${sessionId}`)
      .then((detail) => {
        if (!cancelled) setMessages(detail.messages)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t('chat.failedToLoad'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
    // sessionId is derived from urlSessionId — use urlSessionId as dep to avoid
    // re-fetching when React re-renders without a URL change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlSessionId, apiClient, t])

  // Scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount and when session changes
  useEffect(() => {
    inputRef.current?.focus()
  }, [urlSessionId])

  // Track whether the user is scrolled to the bottom
  useEffect(() => {
    const el = scrollAreaRef.current
    if (!el) return
    const onScroll = () => {
      setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 60)
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [])

  const submitMessage = useCallback(
    async (override?: string) => {
      const text = (override ?? input).trim()
      if (!text || sending) return

      setInput('')
      setError(null)
      setSending(true)

      // Reset textarea height
      if (inputRef.current) inputRef.current.style.height = 'auto'

      // Optimistic user message
      const tempUserMsg: ChatMessageOut = {
        message_id: -Date.now(),
        session_id: sessionId ?? 0,
        role: 'user',
        content: text,
        created_at: new Date().toISOString(),
      }
      setMessages((prev) => [...prev, tempUserMsg])

      try {
        let sid = sessionId

        let isNewSession = false

        if (sid === null) {
          // First message — create session (title only), then send the message below
          const session = await apiClient<ChatSessionOut>('/chat/sessions', {
            method: 'POST',
            body: JSON.stringify({ message: text }),
          })
          sid = session.id
          isNewSession = true
          // Skip the load effect — we'll fetch the data right below
          skipLoadRef.current = true
          navigate(`/chat/${sid}`, { replace: true })
        }

        // Send message (first or follow-up — same endpoint)
        await apiClient(`/chat/sessions/${sid}/messages`, {
          method: 'POST',
          body: JSON.stringify({ message: text }),
        })

        // Re-fetch full session to get real messages
        const detail = await apiClient<ChatSessionDetailOut>(`/chat/sessions/${sid}`)
        setMessages(detail.messages)

        // Refresh sidebar only when a new session was created (title added)
        if (isNewSession) refreshSessions()
      } catch (err) {
        // Remove optimistic message on error
        setMessages((prev) => prev.filter((m) => m.message_id !== tempUserMsg.message_id))
        setLastFailedInput(text)
        setError(err instanceof Error ? err.message : t('chat.somethingWentWrong'))
      } finally {
        setSending(false)
        inputRef.current?.focus()
      }
    },
    [apiClient, input, sending, sessionId, navigate, refreshSessions, t],
  )

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    submitMessage()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submitMessage()
    }
  }

  const isEmpty = messages.length === 0 && !sending && !loading

  if (isEmpty) {
    return (
      <div className="relative flex flex-col h-full items-center justify-center px-8">
        <div className="w-full max-w-[680px] flex flex-col items-center gap-6">
          {/* Greeting */}
          <div className="flex flex-col items-center gap-3 mb-2">
            <div className="w-14 h-14 rounded-2xl bg-primary/[0.12] border border-primary/[0.22] flex items-center justify-center text-primary/70">
              <Wine size={28} />
            </div>
            <p className="text-[17px] font-light text-foreground/75">{t('chat.welcome')}</p>
          </div>

          {/* Composer */}
          <form
            onSubmit={handleSubmit}
            className="w-full flex flex-col rounded-xl bg-white/[0.05] border border-border transition-colors"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${e.target.scrollHeight}px`
              }}
              onKeyDown={handleKeyDown}
              placeholder={t('chat.placeholder')}
              maxLength={MAX_MESSAGE_LENGTH}
              rows={1}
              disabled={sending}
              className="bg-transparent text-sm font-light resize-none overflow-y-auto focus:outline-none placeholder:text-muted-foreground/40 disabled:opacity-50 px-4 pt-3 pb-1.5 max-h-32"
            />
            <div className="flex items-center justify-end px-2.5 pb-2.5">
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="w-7 h-7 rounded-full bg-primary/80 text-background flex items-center justify-center hover:bg-primary transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
                aria-label={t('chat.send')}
              >
                <ArrowUp size={14} weight="bold" />
              </button>
            </div>
          </form>

          {/* Starter chips */}
          <div className="flex flex-wrap justify-center gap-2">
            {(t('chat.starters', { returnObjects: true }) as string[]).map((starter) => (
              <button
                key={starter}
                type="button"
                onClick={() => submitMessage(starter)}
                className="px-3.5 py-1.5 rounded-full border border-border/70 bg-white/[0.03] text-[12px] text-foreground/60 hover:border-primary/40 hover:text-foreground hover:bg-accent-glow transition-colors"
              >
                {starter}
              </button>
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="relative flex flex-col h-full">
      {/* Sticky title bar */}
      {sessionTitle && sessionId && (
        <div className="px-8 pt-5 pb-1">
          <SessionTitleBar
            title={sessionTitle}
            onRename={(title) => renameSession(sessionId, title)}
            onDelete={() => deleteSession(sessionId)}
          />
        </div>
      )}

      {/* Messages area */}
      <div
        ref={scrollAreaRef}
        className={`flex-1 overflow-y-auto py-10 transition-[padding-right] duration-300 ease-out ${selectedSku ? 'pr-[376px]' : ''}`}
      >
        <div className="max-w-[680px] mx-auto px-8 flex flex-col gap-7">
          {loading && (
            <div className="flex items-center justify-center min-h-[20vh]">
              <p className="text-sm text-muted-foreground">{t('chat.loading')}</p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div
              key={msg.message_id}
              className={`group/msg flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              {msg.role === 'user' ? (
                <>
                  <div className="max-w-[72%] bg-primary/[0.08] border border-primary/[0.1] rounded-2xl px-4 py-3">
                    <p className="text-sm leading-relaxed whitespace-pre-wrap">
                      {msg.content as string}
                    </p>
                  </div>
                  <UserMessageActions
                    text={msg.content as string}
                    createdAt={msg.created_at}
                    onRegenerate={
                      i === lastUserIdx && !sending
                        ? () => submitMessage(msg.content as string)
                        : undefined
                    }
                  />
                </>
              ) : (
                <>
                  <div className="w-full bg-white/[0.025] border border-border rounded-2xl px-5 py-[18px]">
                    <AssistantMessage
                      content={msg.content}
                      storeNames={storeNames}
                      selectedSku={selectedSku}
                      setSelectedSku={setSelectedSku}
                    />
                  </div>
                  <AssistantMessageActions
                    content={msg.content}
                    alwaysVisible={i === lastAssistantIdx && !sending}
                    onRegenerate={
                      i === lastAssistantIdx && !sending && lastUserMsg
                        ? () => submitMessage(lastUserMsg)
                        : undefined
                    }
                  />
                </>
              )}
            </div>
          ))}

          {sending && (
            <div className="flex items-start">
              <div className="w-full bg-white/[0.025] border border-border rounded-2xl">
                <ThinkingIndicator />
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start">
              <p className="text-sm text-destructive">
                {error} —{' '}
                {lastFailedInput && (
                  <>
                    <button
                      type="button"
                      className="underline underline-offset-4 hover:text-foreground"
                      onClick={() => {
                        setInput(lastFailedInput)
                        setError(null)
                        setLastFailedInput(null)
                        inputRef.current?.focus()
                      }}
                    >
                      {t('chat.retry')}
                    </button>
                    {' · '}
                  </>
                )}
                <button
                  type="button"
                  className="underline underline-offset-4 hover:text-foreground"
                  onClick={() => {
                    setError(null)
                    setLastFailedInput(null)
                  }}
                >
                  {t('chat.dismiss')}
                </button>
              </p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Scroll-to-bottom button */}
      {!atBottom && (
        <div className="absolute bottom-32 left-1/2 -translate-x-1/2 z-10">
          <button
            type="button"
            onClick={() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' })}
            className="flex items-center justify-center w-9 h-9 rounded-full bg-secondary border border-border text-foreground/50 hover:text-foreground shadow-lg transition-colors"
          >
            <ArrowDown size={16} />
          </button>
        </div>
      )}

      {/* Input area — bg-background covers scrolled content beneath */}
      <div
        className={`flex-shrink-0 w-full pb-6 pt-2 bg-background relative before:absolute before:inset-x-0 before:-top-8 before:h-8 before:bg-gradient-to-t before:from-background before:to-transparent before:pointer-events-none transition-[padding-right] duration-300 ease-out ${selectedSku ? 'pr-[376px]' : ''}`}
      >
        <div className="max-w-[680px] w-full mx-auto px-8">
          <form
            onSubmit={handleSubmit}
            className="flex flex-col rounded-xl bg-white/[0.04] transition-colors"
          >
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value)
                e.target.style.height = 'auto'
                e.target.style.height = `${e.target.scrollHeight}px`
              }}
              onKeyDown={handleKeyDown}
              placeholder={t('chat.placeholder')}
              maxLength={MAX_MESSAGE_LENGTH}
              rows={1}
              disabled={sending}
              className="bg-transparent text-sm font-light resize-none overflow-y-auto focus:outline-none placeholder:text-muted-foreground/40 disabled:opacity-50 px-4 pt-3 pb-1.5 max-h-32"
            />
            <div className="flex items-center justify-end px-2.5 pb-2.5">
              <button
                type="submit"
                disabled={sending || !input.trim()}
                className="w-7 h-7 rounded-full bg-primary/80 text-background flex items-center justify-center hover:bg-primary transition-colors disabled:opacity-20 disabled:cursor-not-allowed"
                aria-label={t('chat.send')}
              >
                <ArrowUp size={14} weight="bold" />
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default ChatPage
