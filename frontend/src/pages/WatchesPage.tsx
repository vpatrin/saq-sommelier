import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type { ProductOut, WatchWithProduct, UserStorePreferenceOut } from '@/lib/types'
import { Button } from '@/components/ui/button'
import { formatOrigin } from '@/lib/utils'

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
          className="text-green-500 hover:underline underline-offset-4 cursor-pointer"
          onClick={() => onToggleExpand(sku)}
        >
          {storeText}
        </button>
      ) : (
        <span className="text-green-500">{storeText}</span>
      )
    ) : !hasSavedStores && genericStoreCount > 0 ? (
      <span className="text-green-500">
        {t('availability.inStores', { count: genericStoreCount })}
      </span>
    ) : null

  const unavailable = !isOnline && !inStore

  return (
    <div className="flex flex-col gap-1 text-sm mt-1">
      <div className="flex flex-wrap gap-x-1 gap-y-1">
        {unavailable && hasSavedStores ? (
          <span className="text-muted-foreground">{t('availability.unavailable')}</span>
        ) : (
          <>
            {isOnline && <span className="text-green-500">{t('availability.online')}</span>}
            {isOnline && storeNode && <span className="text-muted-foreground">·</span>}
            {storeNode}
          </>
        )}
      </div>
      {isExpanded && canExpand && (
        <ul className="text-muted-foreground text-xs ml-1">
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

  const [watches, setWatches] = useState<WatchWithProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set())

  const userId = `tg:${user?.telegram_id}`

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
      setRemoving(sku)
      try {
        await apiClient(`/watches/${sku}?user_id=${encodeURIComponent(userId)}`, {
          method: 'DELETE',
        })
        // Remove from local state — no need to re-fetch the full list
        setWatches((prev) => prev.filter((w) => w.watch.sku !== sku))
      } catch (err) {
        setError(err instanceof ApiError ? err.detail : t('watches.failedToRemove'))
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground font-mono">{t('watches.loading')}</p>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-mono font-bold mb-6">{t('watches.title')}</h1>

        {error && <p className="text-destructive text-sm font-mono mb-4">{error}</p>}

        {watches.length === 0 ? (
          <p className="text-muted-foreground font-mono">{t('watches.empty')}</p>
        ) : (
          <ul className="flex flex-col gap-4">
            {watches.map(({ watch, product }) => (
              <li
                key={watch.sku}
                className="border border-border p-4 flex justify-between items-start gap-4"
              >
                <div className="flex-1 min-w-0">
                  {product ? (
                    <>
                      <p className="font-mono font-bold truncate">
                        {product.url ? (
                          <a
                            href={product.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-primary"
                          >
                            {product.name}
                          </a>
                        ) : (
                          product.name
                        )}
                      </p>
                      <p className="text-sm text-muted-foreground mt-1">
                        {[product.grape, formatOrigin(product), product.vintage]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                      {product.price && <p className="text-sm mt-1">${product.price}</p>}
                      <AvailabilityStatus
                        product={product}
                        sku={watch.sku}
                        storeNames={storeNames}
                        expandedStores={expandedStores}
                        onToggleExpand={handleToggleExpand}
                      />
                    </>
                  ) : (
                    <p className="text-muted-foreground font-mono">
                      {t('watches.delisted', { sku: watch.sku })}
                    </p>
                  )}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleRemove(watch.sku)}
                  disabled={removing === watch.sku}
                >
                  {removing === watch.sku ? t('watches.removing') : t('watches.remove')}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default WatchesPage
