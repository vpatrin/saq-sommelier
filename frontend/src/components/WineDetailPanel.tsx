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

  const userId = `tg:${user?.telegram_id}`

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
        <div className="px-5 pt-5 pb-4 border-b border-border/50">
          <div className="flex items-center gap-2 mb-3">
            {dotColor && <span className={`w-2 h-2 rounded-full shrink-0 ${dotColor}`} />}
            {p.category && (
              <span className="text-[11px] text-muted-foreground/60">{p.category}</span>
            )}
          </div>
          <h2 className="text-[15px] font-medium leading-snug line-clamp-3 mb-1">
            {p.name ?? p.sku}
          </h2>
          {(p.producer || p.vintage) && (
            <p className="text-[12px] text-muted-foreground/60">
              {[p.producer, p.vintage].filter(Boolean).join(' · ')}
            </p>
          )}
          {p.taste_tag && (
            <span className="inline-block mt-2 text-[11px] px-2 py-0.5 rounded border bg-primary/[0.06] text-primary/60 border-primary/15">
              {p.taste_tag}
            </span>
          )}
        </div>

        <div className="px-5 py-4 border-b border-border/50 flex items-center gap-3">
          <span className="font-mono text-[18px] text-primary whitespace-nowrap">
            {p.price ? `${p.price} $` : '—'}
          </span>
          {p.size && <span className="text-[11px] text-muted-foreground/50">{p.size}</span>}
          <div className="flex-1" />
          <button
            type="button"
            disabled={isBusy}
            onClick={() => sku && (isWatched ? handleUnwatch(sku) : handleWatch(sku))}
            className={`w-28 justify-center flex items-center gap-1.5 border rounded-lg px-3 py-1.5 text-[12px] transition-colors shrink-0 ${
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
            className="w-7 h-7 flex items-center justify-center rounded-lg border border-border text-muted-foreground/20 cursor-not-allowed"
          >
            <ChartDonut size={13} />
          </button>
          <button
            type="button"
            disabled
            title={t('userMenu.soon')}
            className="w-7 h-7 flex items-center justify-center rounded-lg border border-border text-muted-foreground/20 cursor-not-allowed"
          >
            <NotePencil size={13} />
          </button>
        </div>

        {details.length > 0 && (
          <div className="px-5 py-4 border-b border-border/50">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2.5">
              {details.map(({ label, value }) => (
                <div key={label}>
                  <dt className="text-[10px] text-muted-foreground/40 uppercase tracking-wider mb-0.5">
                    {label}
                  </dt>
                  <dd className="text-[13px]">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}

        {grapes && (
          <div className="px-5 py-4 border-b border-border/50">
            <p className="text-[10px] text-muted-foreground/40 uppercase tracking-wider mb-1.5">
              {t('wineDetail.grapes')}
            </p>
            <p className="text-[13px] text-muted-foreground">{grapes}</p>
          </div>
        )}

        <div className="px-5 py-4 border-b border-border/50">
          <p className="text-[10px] text-muted-foreground/40 uppercase tracking-wider mb-3">
            {t('wineDetail.availability')}
          </p>
          {p.online_availability && (
            <div className="flex items-center gap-2 mb-2">
              <span className="w-2 h-2 rounded-full bg-emerald-500/80 shrink-0" />
              <span className="text-[13px] text-muted-foreground">{t('availability.online')}</span>
            </div>
          )}
          {storeIds.length === 0 ? (
            <p className="text-[12px] text-muted-foreground/40">
              {t('wineDetail.noStores')}{' '}
              <Link
                to="/stores"
                className="underline hover:text-muted-foreground transition-colors"
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
                      className={`w-2 h-2 rounded-full shrink-0 ${
                        available ? 'bg-emerald-500/80' : 'bg-red-500/40'
                      }`}
                    />
                    <span
                      className={`text-[13px] truncate ${
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
              className="flex items-center gap-2 text-[12px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
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
      className={`absolute top-0 right-0 bottom-0 w-[360px] bg-sidebar border-l border-border flex flex-col z-10 transition-transform duration-300 ease-out ${
        sku ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div className="flex items-center gap-2 px-5 py-4 border-b border-border shrink-0">
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-1.5 text-muted-foreground/50 hover:text-muted-foreground transition-colors text-[12px]"
        >
          <ArrowLeft size={13} />
          {t('wineDetail.close')}
        </button>
        <div className="flex-1" />
      </div>

      <div className="flex-1 overflow-y-auto min-h-0">
        {isLoading && <PanelSkeleton />}

        {panelState.status === 'error' && !isLoading && (
          <div className="px-5 py-8 text-center">
            <p className="text-[13px] text-muted-foreground">
              {panelState.message}
              {' — '}
              <button
                type="button"
                onClick={() => sku && fetchProduct(sku)}
                className="underline hover:text-foreground transition-colors"
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
    <div className="px-5 py-5 flex flex-col gap-4 animate-pulse">
      <div className="flex flex-col gap-2 pb-4 border-b border-border/50">
        <div className="h-3 w-16 bg-white/[0.06] rounded" />
        <div className="h-5 w-full bg-white/[0.06] rounded" />
        <div className="h-5 w-3/4 bg-white/[0.06] rounded" />
        <div className="h-3 w-1/2 bg-white/[0.04] rounded mt-1" />
      </div>
      <div className="flex items-center gap-3 pb-4 border-b border-border/50">
        <div className="h-6 w-20 bg-white/[0.06] rounded" />
        <div className="flex-1" />
        <div className="h-7 w-24 bg-white/[0.04] rounded-lg" />
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 pb-4 border-b border-border/50">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="flex flex-col gap-1">
            <div className="h-2 w-12 bg-white/[0.04] rounded" />
            <div className="h-4 w-20 bg-white/[0.06] rounded" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {[...Array(2)].map((_, i) => (
          <div key={i} className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-white/[0.06]" />
            <div className="h-3 w-32 bg-white/[0.04] rounded" />
          </div>
        ))}
      </div>
    </div>
  )
}

export default WineDetailPanel
