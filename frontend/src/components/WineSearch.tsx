import { useState, useEffect, useRef } from 'react'
import { MagnifyingGlass } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useApiClient } from '@/lib/api'
import type { ProductOut, PaginatedOut } from '@/lib/types'

interface WineSearchProps {
  onSelect: (product: ProductOut) => void
  onCancel: () => void
}

type SearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'results'; products: ProductOut[] }
  | { status: 'empty'; query: string }
  | { status: 'error' }

function WineSearch({ onSelect, onCancel }: WineSearchProps) {
  const apiClient = useApiClient()
  const { t } = useTranslation()
  const inputRef = useRef<HTMLInputElement>(null)

  const [query, setQuery] = useState('')
  const [retryKey, setRetryKey] = useState(0)
  const [searchState, setSearchState] = useState<SearchState>({ status: 'idle' })

  // Autofocus on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
    // onCancel is stable (useCallback in parent) — safe dep
  }, [onCancel])

  // Debounced search — fires 300ms after the user stops typing.
  // Idle reset happens in onChange (not here) to avoid synchronous setState in effect.
  useEffect(() => {
    const q = query.trim()
    if (!q) return

    // AbortController lets us cancel the in-flight fetch if the user types again
    const controller = new AbortController()

    // Set loading inside the timeout so no synchronous setState fires in the effect body
    const timer = setTimeout(async () => {
      setSearchState({ status: 'loading' })
      try {
        const data = await apiClient<PaginatedOut>(
          `/products?q=${encodeURIComponent(q)}&limit=3&scope=wine`,
          { signal: controller.signal },
        )
        if (data.products.length === 0) {
          setSearchState({ status: 'empty', query: q })
        } else {
          setSearchState({ status: 'results', products: data.products })
        }
      } catch (err) {
        // AbortError fires when the controller cancels — not a real error
        if (err instanceof DOMException && err.name === 'AbortError') return
        setSearchState({ status: 'error' })
      }
    }, 300)

    // Cleanup: cancel timer AND abort in-flight request before next effect
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query, retryKey, apiClient])

  return (
    <div>
      <div className="relative mb-2">
        <MagnifyingGlass
          size={14}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
        />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            // Reset to idle immediately when the input is cleared
            if (!e.target.value.trim()) setSearchState({ status: 'idle' })
          }}
          placeholder={t('wineSearch.placeholder')}
          className="w-full h-9 pl-8 pr-3 rounded-lg bg-white/[0.04] border border-border text-[13px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors"
        />
      </div>

      {searchState.status === 'loading' && (
        <div className="flex flex-col gap-1 mt-1">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-9 rounded-lg bg-white/[0.025] border border-border animate-pulse"
            />
          ))}
        </div>
      )}

      {searchState.status === 'results' && (
        <ul className="flex flex-col gap-1 mt-1">
          {searchState.products.map((product) => {
            const meta = [
              product.vintage,
              product.size,
              product.price ? `${product.price} $` : null,
            ]
              .filter(Boolean)
              .join(' · ')

            return (
              <li key={product.sku}>
                <button
                  type="button"
                  onClick={() => onSelect(product)}
                  className="w-full text-left px-3 py-2 rounded-lg border border-transparent hover:border-primary/20 hover:bg-primary/5 transition-colors"
                >
                  <p className="text-[13px] font-medium truncate">{product.name ?? product.sku}</p>
                  {meta && <p className="text-[11px] text-muted-foreground/50 truncate">{meta}</p>}
                </button>
              </li>
            )
          })}
        </ul>
      )}

      {searchState.status === 'empty' && (
        <p className="text-[12px] text-muted-foreground/50 mt-2 px-1">
          {t('wineSearch.noResults')} « {searchState.query} »
        </p>
      )}

      {searchState.status === 'error' && (
        <p className="text-[12px] text-muted-foreground/50 mt-2 px-1">
          {t('wineSearch.failedToSearch')}{' '}
          <button
            type="button"
            className="underline hover:text-foreground transition-colors"
            onClick={() => setRetryKey((k) => k + 1)}
          >
            {t('wineSearch.retry')}
          </button>
        </p>
      )}
    </div>
  )
}

export default WineSearch
