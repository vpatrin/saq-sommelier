import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useTranslation } from 'react-i18next'
import {
  ArrowSquareOutIcon as ArrowSquareOut,
  HeartIcon as Heart,
  NotePencilIcon as NotePencil,
  ChartDonutIcon as ChartDonut,
  ArrowLeftIcon as ArrowLeft,
} from '@phosphor-icons/react'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type { ProductOut, UserStorePreferenceOut, WatchWithProduct } from '@/lib/types'
import { CATEGORY_DOT, formatOrigin } from '@/lib/utils'

interface WineDetailPanelProps {
  sku: string | null
  onClose: () => void
}

type PanelState =
  | { status: 'idle' }
  | { status: 'error'; message: string }
  | { status: 'loaded'; product: ProductOut }

function WineDetailPanel({ sku, onClose }: WineDetailPanelProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const apiClient = useApiClient()

  const userId = `user:${user?.id}`

  const [loadedSku, setLoadedSku] = useState<string | null>(null)
  const [panelState, setPanelState] = useState<PanelState>({ status: 'idle' })

  const [watchedSkus, setWatchedSkus] = useState<Set<string>>(new Set())
  const [watchingInProgress, setWatchingInProgress] = useState<string | null>(null)
  const [storeIds, setStoreIds] = useState<string[]>([])
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())

  // loadedSku tracks what's currently shown; when sku differs, show skeleton
  const isLoading = sku !== null && loadedSku !== sku

  // Tracks whether we've already fetched watches+stores for this open session.
  // Resets to false when the panel closes (sku → null), so the next open re-fetches.
  const hasFetchedOnOpen = useRef(false)

  useEffect(() => {
    if (!sku) {
      hasFetchedOnOpen.current = false
      return
    }
    if (hasFetchedOnOpen.current) return
    hasFetchedOnOpen.current = true

    let cancelled = false

    async function fetchWatches() {
      try {
        const data = await apiClient<WatchWithProduct[]>(
          `/watches?user_id=${encodeURIComponent(userId)}`,
        )
        if (!cancelled) setWatchedSkus(new Set(data.map((w) => w.watch.sku)))
      } catch {
        // Non-critical — watch button defaults to "Watch"
      }
    }

    async function fetchStores() {
      try {
        const prefs = await apiClient<UserStorePreferenceOut[]>('/stores/preferences')
        if (!cancelled) {
          setStoreIds(prefs.map((p) => p.saq_store_id).sort())
          setStoreNames(new Map(prefs.map((p) => [p.saq_store_id, p.store.name])))
        }
      } catch {
        // Non-critical — availability section shows "save stores" prompt
      }
    }

    fetchWatches()
    fetchStores()
    return () => {
      cancelled = true
    }
  }, [sku, apiClient, userId])

  const fetchProduct = useCallback(
    (targetSku: string) => {
      setLoadedSku(null)
      apiClient<ProductOut>(`/products/${targetSku}`)
        .then((data) => {
          setPanelState({ status: 'loaded', product: data })
          setLoadedSku(targetSku)
        })
        .catch((err) => {
          setPanelState({
            status: 'error',
            message: err instanceof ApiError ? err.detail : t('wineDetail.failedToLoad'),
          })
          setLoadedSku(targetSku)
        })
    },
    [apiClient, t],
  )

  useEffect(() => {
    if (!sku) return
    let cancelled = false
    apiClient<ProductOut>(`/products/${sku}`)
      .then((data) => {
        if (!cancelled) {
          setPanelState({ status: 'loaded', product: data })
          setLoadedSku(sku)
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setPanelState({
            status: 'error',
            message: err instanceof ApiError ? err.detail : t('wineDetail.failedToLoad'),
          })
          setLoadedSku(sku)
        }
      })
    return () => {
      cancelled = true
    }
  }, [sku, apiClient, t])

  useEffect(() => {
    if (!sku) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [sku, onClose])

  const handleWatch = useCallback(
    async (targetSku: string) => {
      setWatchingInProgress(targetSku)
      setWatchedSkus((prev) => new Set([...prev, targetSku]))
      try {
        await apiClient(`/watches?user_id=${encodeURIComponent(userId)}`, {
          method: 'POST',
          body: JSON.stringify({ sku: targetSku }),
        })
      } catch {
        setWatchedSkus((prev) => {
          const next = new Set(prev)
          next.delete(targetSku)
          return next
        })
      } finally {
        setWatchingInProgress(null)
      }
    },
    [apiClient, userId],
  )

  const handleUnwatch = useCallback(
    async (targetSku: string) => {
      setWatchingInProgress(targetSku)
      setWatchedSkus((prev) => {
        const next = new Set(prev)
        next.delete(targetSku)
        return next
      })
      try {
        await apiClient(`/watches/${targetSku}?user_id=${encodeURIComponent(userId)}`, {
          method: 'DELETE',
        })
      } catch {
        setWatchedSkus((prev) => new Set([...prev, targetSku]))
      } finally {
        setWatchingInProgress(null)
      }
    },
    [apiClient, userId],
  )

  const isWatched = sku ? watchedSkus.has(sku) : false
  const isBusy = sku ? watchingInProgress === sku : false

  let content: React.ReactNode = null
  if (panelState.status === 'loaded' && !isLoading) {
    const p = panelState.product
    const dotColor = p.category ? (CATEGORY_DOT[p.category] ?? 'bg-muted-foreground/30') : null
    const origin = formatOrigin(p)
    const grapes = p.grape ?? null

    const details: { label: string; value: string }[] = []
    if (origin) details.push({ label: t('wineDetail.region'), value: origin })
    if (p.appellation) details.push({ label: t('wineDetail.appellation'), value: p.appellation })
    if (p.alcohol) details.push({ label: t('wineDetail.alcohol'), value: p.alcohol })
    if (p.sugar) details.push({ label: t('wineDetail.sugar'), value: p.sugar })

    content = (
      <>
        <div className="border-border/50 border-b px-5 pt-5 pb-4">
          <div className="mb-3 flex items-center gap-2">
            {dotColor && <span className={`h-2 w-2 shrink-0 rounded-full ${dotColor}`} />}
            {p.category && (
              <span className="text-muted-foreground/60 text-[11px]">{p.category}</span>
            )}
          </div>
          <h2 className="mb-1 line-clamp-3 text-[15px] leading-snug font-medium">
            {p.name ?? p.sku}
          </h2>
          {(p.producer || p.vintage) && (
            <p className="text-muted-foreground/60 text-[12px]">
              {[p.producer, p.vintage].filter(Boolean).join(' · ')}
            </p>
          )}
          {p.taste_tag && (
            <span className="bg-primary/[0.06] text-primary/60 border-primary/15 mt-2 inline-block rounded border px-2 py-0.5 text-[11px]">
              {p.taste_tag}
            </span>
          )}
        </div>

        <div className="border-border/50 flex items-center gap-3 border-b px-5 py-4">
          <span className="text-primary font-mono text-[18px] whitespace-nowrap">
            {p.price ? `${p.price} $` : '—'}
          </span>
          {p.size && <span className="text-muted-foreground/50 text-[11px]">{p.size}</span>}
          <div className="flex-1" />
          <button
            type="button"
            disabled={isBusy}
            onClick={() => sku && (isWatched ? handleUnwatch(sku) : handleWatch(sku))}
            className={`flex w-28 shrink-0 items-center justify-center gap-1.5 rounded-lg border px-3 py-1.5 text-[12px] transition-colors ${
              isWatched
                ? 'border-primary/40 bg-primary/10 text-primary'
                : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80'
            } ${isBusy ? 'opacity-50' : ''}`}
          >
            <Heart size={13} weight={isWatched ? 'fill' : 'regular'} />
            {isBusy ? '...' : isWatched ? t('search.watching') : t('search.watch')}
          </button>
          <button
            type="button"
            disabled
            title={t('userMenu.soon')}
            className="border-border text-muted-foreground/20 flex h-7 w-7 cursor-not-allowed items-center justify-center rounded-lg border"
          >
            <ChartDonut size={13} />
          </button>
          <button
            type="button"
            disabled
            title={t('userMenu.soon')}
            className="border-border text-muted-foreground/20 flex h-7 w-7 cursor-not-allowed items-center justify-center rounded-lg border"
          >
            <NotePencil size={13} />
          </button>
        </div>

        {details.length > 0 && (
          <div className="border-border/50 border-b px-5 py-4">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
              {details.map(({ label, value }) => (
                <div key={label}>
                  <dt className="text-muted-foreground/40 mb-0.5 text-[10px] tracking-wider uppercase">
                    {label}
                  </dt>
                  <dd className="text-[13px]">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {grapes && (
          <div className="border-border/50 border-b px-5 py-4">
            <p className="text-muted-foreground/40 mb-1.5 text-[10px] tracking-wider uppercase">
              {t('wineDetail.grapes')}
            </p>
            <p className="text-muted-foreground text-[13px]">{grapes}</p>
          </div>
        )}

        <div className="border-border/50 border-b px-5 py-4">
          <p className="text-muted-foreground/40 mb-3 text-[10px] tracking-wider uppercase">
            {t('wineDetail.availability')}
          </p>
          {p.online_availability && (
            <div className="mb-2 flex items-center gap-2">
              <span className="h-2 w-2 shrink-0 rounded-full bg-emerald-500/80" />
              <span className="text-muted-foreground text-[13px]">{t('availability.online')}</span>
            </div>
          )}
          {storeIds.length === 0 ? (
            <p className="text-muted-foreground/40 text-[12px]">
              {t('wineDetail.noStores')}{' '}
              <Link
                to="/stores"
                className="hover:text-muted-foreground underline transition-colors"
              >
                {t('wineDetail.saveStores')}
              </Link>
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {storeIds.map((id) => {
                const available = p.store_availability?.includes(id) ?? false
                const name = storeNames.get(id) ?? id
                return (
                  <div key={id} className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        available ? 'bg-emerald-500/80' : 'bg-red-500/40'
                      }`}
                    />
                    <span
                      className={`truncate text-[13px] ${
                        available ? 'text-muted-foreground' : 'text-muted-foreground/40'
                      }`}
                    >
                      {name}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {p.url && (
          <div className="px-5 py-4">
            <a
              href={p.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-muted-foreground/50 hover:text-muted-foreground flex items-center gap-2 text-[12px] transition-colors"
            >
              <ArrowSquareOut size={13} />
              {t('wineDetail.viewOnSaq')}
            </a>
          </div>
        )}
      </>
    )
  }

  return (
    <div
      className={`bg-sidebar border-border absolute top-0 right-0 bottom-0 z-10 flex w-[360px] flex-col border-l transition-transform duration-300 ease-out ${
        sku ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div className="border-border flex shrink-0 items-center gap-2 border-b px-5 py-4">
        <button
          type="button"
          onClick={onClose}
          className="text-muted-foreground/50 hover:text-muted-foreground flex items-center gap-1.5 text-[12px] transition-colors"
        >
          <ArrowLeft size={13} />
          {t('wineDetail.close')}
        </button>
        <div className="flex-1" />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading && <PanelSkeleton />}

        {panelState.status === 'error' && !isLoading && (
          <div className="px-5 py-8 text-center">
            <p className="text-muted-foreground text-[13px]">
              {panelState.message}
              {' — '}
              <button
                type="button"
                onClick={() => sku && fetchProduct(sku)}
                className="hover:text-foreground underline transition-colors"
              >
                {t('wineDetail.retry')}
              </button>
            </p>
          </div>
        )}

        {content}
      </div>
    </div>
  )
}

function PanelSkeleton() {
  return (
    <div className="flex animate-pulse flex-col gap-4 px-5 py-5">
      <div className="border-border/50 flex flex-col gap-2 border-b pb-4">
        <div className="h-3 w-16 rounded bg-white/[0.06]" />
        <div className="h-5 w-full rounded bg-white/[0.06]" />
        <div className="h-5 w-3/4 rounded bg-white/[0.06]" />
        <div className="mt-1 h-3 w-1/2 rounded bg-white/[0.04]" />
      </div>
      <div className="border-border/50 flex items-center gap-3 border-b pb-4">
        <div className="h-6 w-20 rounded bg-white/[0.06]" />
        <div className="flex-1" />
        <div className="h-7 w-24 rounded-lg bg-white/[0.04]" />
      </div>
      <div className="border-border/50 grid grid-cols-2 gap-x-4 gap-y-3 border-b pb-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex flex-col gap-1">
            <div className="h-2 w-12 rounded bg-white/[0.04]" />
            <div className="h-4 w-20 rounded bg-white/[0.06]" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="h-2 w-2 rounded-full bg-white/[0.06]" />
            <div className="h-3 w-32 rounded bg-white/[0.04]" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default WineDetailPanel
