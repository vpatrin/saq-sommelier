import { useState, useRef, useEffect, useCallback } from 'react'
import { useApiClient } from '@/lib/api'
import { formatOrigin } from '@/lib/utils'
import type {
  ChatSessionOut,
  ChatMessageOut,
  ChatSessionDetailOut,
  RecommendationOut,
  ProductOut,
} from '@/lib/types'

const MAX_MESSAGE_LENGTH = 2000

function isRecommendation(content: string | RecommendationOut): content is RecommendationOut {
  return typeof content === 'object' && 'products' in content
}

function WineCard({ product, reason }: { product: ProductOut; reason: string }) {
  const origin = formatOrigin(product)
  return (
    <div className="border border-border p-3">
      {product.url ? (
        <a
          href={product.url}
          target="_blank"
          rel="noopener noreferrer"
          className="font-mono font-bold text-sm line-clamp-2 hover:text-primary"
        >
          {product.name}
        </a>
      ) : (
        <p className="font-mono font-bold text-sm line-clamp-2">{product.name}</p>
      )}
      <p className="text-xs text-muted-foreground mt-0.5">
        {[origin, product.category, product.price ? `${product.price} $` : null]
          .filter(Boolean)
          .join(' · ')}
      </p>
      <p className="text-sm mt-2">{reason}</p>
    </div>
  )
}

function AssistantMessage({ content }: { content: string | RecommendationOut }) {
  if (!isRecommendation(content)) {
    return <p className="text-sm whitespace-pre-wrap">{content}</p>
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm">{content.summary}</p>
      {content.products.map(({ product, reason }) => (
        <WineCard key={product.sku} product={product} reason={reason} />
      ))}
    </div>
  )
}

function ChatPage() {
  const apiClient = useApiClient()
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [messages, setMessages] = useState<ChatMessageOut[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastFailedInput, setLastFailedInput] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  // Scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const submitMessage = useCallback(async () => {
    const text = input.trim()
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

      if (sid === null) {
        // First message — create session, then send the message
        const session = await apiClient<ChatSessionOut>('/chat/sessions', {
          method: 'POST',
          body: JSON.stringify({ message: text }),
        })
        sid = session.id
        setSessionId(sid)
      }

      // Send message (first or follow-up — same endpoint)
      await apiClient(`/chat/sessions/${sid}/messages`, {
        method: 'POST',
        body: JSON.stringify({ message: text }),
      })

      // Re-fetch full session to get real messages
      const detail = await apiClient<ChatSessionDetailOut>(`/chat/sessions/${sid}`)
      setMessages(detail.messages)
    } catch (err) {
      // Remove optimistic message on error
      setMessages((prev) => prev.filter((m) => m.message_id !== tempUserMsg.message_id))
      setLastFailedInput(text)
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }, [apiClient, input, sending, sessionId])

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
          {messages.length === 0 && !sending && (
            <div className="flex flex-col items-center justify-center h-full min-h-[40vh] gap-2">
              <h1 className="text-2xl font-mono font-bold">What are you drinking tonight?</h1>
              <p className="text-muted-foreground text-sm">
                Ask for a recommendation — try "A bold red under $30" or "Something for sushi"
              </p>
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
                  <AssistantMessage content={msg.content} />
                )}
              </div>
            </div>
          ))}

          {sending && (
            <div className="flex flex-col gap-1 items-start">
              <div className="max-w-[85%]">
                <p className="text-sm text-muted-foreground font-mono">Thinking...</p>
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
                      retry
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
                  dismiss
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
            placeholder="Ask the sommelier..."
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
            Send
          </button>
        </form>
      </div>
    </div>
  )
}

export default ChatPage
