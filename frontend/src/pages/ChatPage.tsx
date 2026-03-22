import { useState, useRef, useEffect, useCallback } from 'react'
import { useParams, useNavigate, useOutletContext } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useApiClient } from '@/lib/api'
import type { ChatOutletContext } from '@/components/AppShell'
import WineCard from '@/components/WineCard'
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

function AssistantMessage({
  content,
  storeNames,
  expandedStores,
  onToggleStores,
}: {
  content: string | RecommendationOut
  storeNames: Map<string, string>
  expandedStores: Set<string>
  onToggleStores: (sku: string) => void
}) {
  if (!isRecommendation(content)) {
    return <p className="text-sm whitespace-pre-wrap">{content}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">{content.summary}</p>
      {content.products.map(({ product, reason }) => (
        <div key={product.sku} className="border border-border p-4">
          <WineCard
            product={product}
            reason={reason}
            storeNames={storeNames}
            storesExpanded={expandedStores.has(product.sku)}
            onToggleStores={() => onToggleStores(product.sku)}
          />
        </div>
      ))}
    </div>
  )
}

function ChatPage() {
  const { t } = useTranslation()
  const apiClient = useApiClient()
  const navigate = useNavigate()
  const { sessionId: urlSessionId } = useParams<{ sessionId: string }>()
  const { refreshSessions } = useOutletContext<ChatOutletContext>()

  // Derive sessionId directly from URL — no intermediate state to get stale
  const sessionId = urlSessionId ? Number(urlSessionId) : null

  const [messages, setMessages] = useState<ChatMessageOut[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFailedInput, setLastFailedInput] = useState<string | null>(null)
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set())
  const toggleStoreExpand = useCallback((sku: string) => {
    setExpandedStores((prev) => {
      const next = new Set(prev)
      if (next.has(sku)) next.delete(sku)
      else next.add(sku)
      return next
    })
  }, [])
  const bottomRef = useRef<HTMLDivElement>(null)
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

  // Reset transient state when URL changes (new chat vs resume)
  useEffect(() => {
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    submitMessage()
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submitMessage()
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-2xl mx-auto flex flex-col gap-6">
          {messages.length === 0 && !sending && !loading && (
            <div className="flex flex-col items-center justify-center h-full min-h-[40vh] gap-6">
              <h1 className="text-2xl font-mono font-bold">{t('chat.welcome')}</h1>
              <div className="grid grid-cols-2 gap-2 w-full max-w-lg">
                {(t('chat.starters', { returnObjects: true }) as string[]).map((starter) => (
                  <button
                    key={starter}
                    type="button"
                    onClick={() => submitMessage(starter)}
                    className="border border-border px-4 py-3 text-sm font-mono text-left hover:bg-muted"
                  >
                    {starter}
                  </button>
                ))}
              </div>
            </div>
          )}

          {loading && (
            <div className="flex flex-col items-center justify-center min-h-[20vh]">
              <p className="text-sm text-muted-foreground font-mono">{t('chat.loading')}</p>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.message_id}
              className={`flex flex-col gap-1 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] ${
                  msg.role === 'user' ? 'bg-primary/10 border border-primary/20 px-4 py-2' : ''
                }`}
              >
                {msg.role === 'user' ? (
                  <p className="text-sm whitespace-pre-wrap">{msg.content as string}</p>
                ) : (
                  <AssistantMessage
                    content={msg.content}
                    storeNames={storeNames}
                    expandedStores={expandedStores}
                    onToggleStores={toggleStoreExpand}
                  />
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex flex-col gap-1 items-start">
              <div className="max-w-[85%]">
                <p className="text-sm text-muted-foreground font-mono">{t('chat.thinking')}</p>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2">
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

      {/* Input area */}
      <div className="p-4">
        <form onSubmit={handleSubmit} className="max-w-2xl mx-auto flex gap-2">
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
            className="flex-1 max-h-32 bg-background border border-border px-3 py-2 text-sm font-mono resize-none overflow-y-auto focus:outline-none focus:border-ring disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={sending || !input.trim()}
            className="self-end border border-border px-4 py-2 text-sm font-mono hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('chat.send')}
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatPage
