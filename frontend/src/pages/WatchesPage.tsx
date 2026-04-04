import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { MagnifyingGlass, BookmarkSimple, X } from '@phosphor-icons/react'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type { ProductOut, WatchWithProduct, UserStorePreferenceOut } from '@/lib/types'
import { formatOrigin, CATEGORY_DOT } from '@/lib/utils'
import EmptyState from '@/components/EmptyState'
import { useWineDetail } from '@/contexts/WineDetailContext'

function AvailabilityStatus({
  product,
  sku,
  storeNames,
  expandedStores,
  onToggleExpand,
}: {
  product: ProductOut
  sku: string
  storeNames: Map<string, string>
  expandedStores: Set<string>
  onToggleExpand: (sku: string) => void
}) {
  const { t } = useTranslation()
  const storeAvail = product.store_availability ?? []
  const matchingIds = storeAvail.filter((id) => storeNames.has(id))
  const hasSavedStores = storeNames.size > 0
  const isOnline = product.online_availability === true
  const inStore = matchingIds.length > 0
  const isExpanded = expandedStores.has(sku)
  const canExpand = inStore && matchingIds.length > 1

  const storeText =
    matchingIds.length === 1
      ? t('availability.atStore', { store: storeNames.get(matchingIds[0]) })
      : t('availability.inYourStores', { count: matchingIds.length })

  const genericStoreCount = storeAvail.length
  const storeNode =
    hasSavedStores && inStore ? (
      canExpand ? (
        <button
          type="button"
          className="text-[10px] text-green-500 hover:underline underline-offset-4 cursor-pointer"
          onClick={() => onToggleExpand(sku)}
        >
          {storeText}
        </button>
      ) : (
        <span className="text-[10px] text-green-500">{storeText}</span>
      )
    ) : !hasSavedStores && genericStoreCount > 0 ? (
      <span className="text-[10px] text-green-500">
        {t('availability.inStores', { count: genericStoreCount })}
      </span>
    ) : null

  const unavailable = !isOnline && !inStore

  return (
    <div className="flex flex-col gap-1 mt-1.5">
      <div className="flex flex-wrap gap-x-1 gap-y-1">
        {unavailable && hasSavedStores ? (
          <span className="text-[10px] text-muted-foreground/60">
            {t('availability.unavailable')}
          </span>
        ) : (
          <>
            {isOnline && (
              <span className="text-[10px] text-green-500">{t('availability.online')}</span>
            )}
            {isOnline && storeNode && (
              <span className="text-[10px] text-muted-foreground/50">·</span>
            )}
            {storeNode}
          </>
        )}
      </div>
      {isExpanded && canExpand && (
        <ul className="text-muted-foreground text-[10px] ml-1 mt-0.5 flex flex-col gap-0.5">
          {matchingIds.map((id) => (
            <li key={id}>{storeNames.get(id)}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

function WatchesPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const apiClient = useApiClient()
  const navigate = useNavigate()
  const { selectedSku, setSelectedSku } = useWineDetail()

  const [watches, setWatches] = useState<WatchWithProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')

  const userId = `user:${user?.id}`

  useEffect(() => {
    let cancelled = false

    async function fetchWatches() {
      try {
        const data = await apiClient<WatchWithProduct[]>(
          `/watches?user_id=${encodeURIComponent(userId)}`,
        )
        if (!cancelled) {
          setWatches(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : t('watches.failedToLoad'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    // Non-blocking — store prefs failing shouldn't block the watch list
    async function fetchStorePrefs() {
      try {
        const prefs = await apiClient<UserStorePreferenceOut[]>('/stores/preferences')
        if (!cancelled) {
          setStoreNames(new Map(prefs.map((p) => [p.saq_store_id, p.store.name])))
        }
      } catch {
        // Supplementary data — silently degrade to no store matching
      }
    }

    fetchWatches()
    fetchStorePrefs()

    return () => {
      cancelled = true
    }
  }, [userId, apiClient, t])

  const handleRemove = useCallback(
    async (sku: string) => {
      // Optimistic remove
      setWatches((prev) => prev.filter((w) => w.watch.sku !== sku))
      setRemoving(sku)
      try {
        await apiClient(`/watches/${sku}?user_id=${encodeURIComponent(userId)}`, {
          method: 'DELETE',
        })
      } catch (err) {
        // Roll back on failure
        setError(err instanceof ApiError ? err.detail : t('watches.failedToRemove'))
        // Re-fetch to restore correct state
        try {
          const data = await apiClient<WatchWithProduct[]>(
            `/watches?user_id=${encodeURIComponent(userId)}`,
          )
          setWatches(data)
        } catch {
          // If refetch fails too, leave the error message
        }
      } finally {
        setRemoving(null)
      }
    },
    [apiClient, userId, t],
  )

  const handleToggleExpand = useCallback((sku: string) => {
    setExpandedStores((prev) => {
      const next = new Set(prev)
      if (next.has(sku)) {
        next.delete(sku)
      } else {
        next.add(sku)
      }
      return next
    })
  }, [])

  const query = filter.trim().toLowerCase()
  const filtered = query
    ? watches.filter(({ product }) => product?.name?.toLowerCase().includes(query))
    : watches

  if (loading) {
    return (
      <div className="p-8">
        <div className="max-w-2xl mx-auto">
          <div className="flex flex-col gap-3">
            {[...Array(4)].map((_, i) => (
              <div
                key={i}
                className="h-[72px] rounded-xl bg-white/[0.025] border border-border animate-pulse"
              />
            ))}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 relative overflow-hidden">
      <div
        className={`h-full overflow-y-auto p-8 transition-[padding-right] duration-300 ease-out ${selectedSku ? 'pr-[376px]' : ''}`}
      >
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="flex items-baseline gap-2.5 mb-6">
            <h1 className="text-2xl font-light">{t('watches.title')}</h1>
            {watches.length > 0 && (
              <span className="font-mono text-[11px] text-muted-foreground/60 tabular-nums">
                {watches.length}
              </span>
            )}
          </div>

          {error && (
            <p className="text-destructive text-[13px] mb-4">
              {error}{' '}
              <button
                type="button"
                className="underline underline-offset-4 hover:text-destructive/80"
                onClick={() => setError(null)}
              >
                {t('watches.failedToRemove')}
              </button>
            </p>
          )}

          {watches.length === 0 ? (
            <EmptyState
              icon={<BookmarkSimple size={28} />}
              title={t('watches.emptyTitle')}
              description={t('watches.emptyDesc')}
              cta={{ label: t('watches.emptyCta'), onClick: () => navigate('/search') }}
            />
          ) : (
            <>
              {/* Local search filter */}
              <div className="relative mb-5">
                <MagnifyingGlass
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
                />
                <input
                  type="text"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder={t('watches.filterPlaceholder')}
                  className="w-full h-9 pl-8 pr-3 rounded-lg bg-white/[0.04] border border-border text-[13px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors"
                />
              </div>

              {filtered.length === 0 ? (
                <EmptyState icon={<MagnifyingGlass size={28} />} title={t('watches.noMatch')} />
              ) : (
                <ul className="flex flex-col gap-2">
                  {filtered.map(({ watch, product }) => {
                    const dotColor = product?.category
                      ? (CATEGORY_DOT[product.category] ?? 'bg-muted-foreground/30')
                      : 'bg-muted-foreground/30'
                    const origin = product ? formatOrigin(product) : null
                    const meta = product
                      ? [origin, product.vintage].filter(Boolean).join(' · ')
                      : null

                    return (
                      <li
                        key={watch.sku}
                        onClick={() =>
                          product && setSelectedSku(selectedSku === watch.sku ? null : watch.sku)
                        }
                        className={`group relative overflow-hidden rounded-xl border border-border bg-white/[0.025] transition-colors hover:border-primary/20 px-[18px] py-3.5 ${product ? 'cursor-pointer' : ''}`}
                      >
                        {/* Warm gradient overlay */}
                        <div className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br from-primary/[0.02] to-transparent" />

                        <div className="relative flex items-start gap-2.5">
                          {/* Availability dot */}
                          <span
                            className={`mt-[5px] w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`}
                          />

                          <div className="flex-1 min-w-0">
                            {product ? (
                              <>
                                {/* Name + price row */}
                                <div className="flex items-start justify-between gap-3">
                                  <p className="text-[14px] font-medium leading-snug min-w-0 flex-1 truncate">
                                    {product.url ? (
                                      <a
                                        href={product.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="hover:text-primary transition-colors"
                                      >
                                        {product.name}
                                      </a>
                                    ) : (
                                      product.name
                                    )}
                                  </p>
                                  {product.price && (
                                    <p className="font-mono text-[14px] font-light text-primary/90 whitespace-nowrap flex-shrink-0">
                                      {product.price} $
                                    </p>
                                  )}
                                </div>

                                {/* Meta */}
                                {meta && (
                                  <p className="text-[11px] text-muted-foreground/60 mt-0.5 leading-snug">
                                    {meta}
                                  </p>
                                )}

                                <AvailabilityStatus
                                  product={product}
                                  sku={watch.sku}
                                  storeNames={storeNames}
                                  expandedStores={expandedStores}
                                  onToggleExpand={handleToggleExpand}
                                />
                              </>
                            ) : (
                              <p className="text-[13px] text-muted-foreground">
                                {t('watches.delisted', { sku: watch.sku })}
                              </p>
                            )}
                          </div>

                          {/* Remove button */}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleRemove(watch.sku)
                            }}
                            disabled={removing === watch.sku}
                            className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-40"
                            aria-label={t('watches.remove')}
                          >
                            <X size={13} weight="bold" />
                          </button>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default WatchesPage
