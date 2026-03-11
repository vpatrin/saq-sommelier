import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type { WatchWithProduct, UserStorePreferenceOut } from '@/lib/types'
import { Button } from '@/components/ui/button'

function WatchesPage() {
  const { user } = useAuth()
  const apiClient = useApiClient()

  const [watches, setWatches] = useState<WatchWithProduct[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set())

  const userId = `tg:${user?.telegram_id}`

  // Fetch watches and saved store preferences in parallel
  useEffect(() => {
    let cancelled = false

    async function fetchData() {
      try {
        const [watchData, prefs] = await Promise.all([
          apiClient<WatchWithProduct[]>(
            `/watches?user_id=${encodeURIComponent(userId)}`
          ),
          apiClient<UserStorePreferenceOut[]>('/stores/preferences'),
        ])
        if (!cancelled) {
          setWatches(watchData)
          setStoreNames(
            new Map(prefs.map((p) => [p.saq_store_id, p.store.name]))
          )
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : 'Failed to load watches')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchData()

    return () => {
      cancelled = true
    }
  }, [userId, apiClient])

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
        setError(err instanceof ApiError ? err.detail : 'Failed to remove watch')
      } finally {
        setRemoving(null)
      }
    },
    [apiClient, userId]
  )

  if (loading) {
    return (
      <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
        <p className="text-muted-foreground font-mono">Loading watches...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-mono font-bold mb-6">My Watches</h1>

        {error && (
          <p className="text-destructive text-sm font-mono mb-4">{error}</p>
        )}

        {watches.length === 0 ? (
          <p className="text-muted-foreground font-mono">
            No watches yet. Use the Telegram bot to add wines to your watch list.
          </p>
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
                        {(() => {
                          // Deduplicate region like "Bourgogne, Bourgogne" → "Bourgogne"
                          const region = product.region
                            ? [...new Set(product.region.split(', '))].join(', ')
                            : null
                          const origin =
                            region && product.country && region !== product.country
                              ? `${region}, ${product.country}`
                              : region || product.country
                          return [product.grape, origin, product.vintage]
                            .filter(Boolean)
                            .join(' · ')
                        })()}
                      </p>
                      {product.price && (
                        <p className="text-sm mt-1">${product.price}</p>
                      )}
                      {(() => {
                        const storeAvail = product.store_availability ?? []
                        const matchingIds = storeAvail.filter((id) => storeNames.has(id))
                        const hasSavedStores = storeNames.size > 0
                        const isOnline = product.online_availability === true
                        const inStore = matchingIds.length > 0
                        const isExpanded = expandedStores.has(watch.sku)

                        const storeText =
                          matchingIds.length === 1
                            ? `At ${storeNames.get(matchingIds[0])}`
                            : `In ${matchingIds.length} of your stores`

                        const toggleExpand = () =>
                          setExpandedStores((prev) => {
                            const next = new Set(prev)
                            if (next.has(watch.sku)) {
                              next.delete(watch.sku)
                            } else {
                              next.add(watch.sku)
                            }
                            return next
                          })

                        const canExpand = inStore && matchingIds.length > 1

                        const storeNode = hasSavedStores && inStore ? (
                          canExpand ? (
                            <button
                              type="button"
                              className="text-green-500 hover:underline underline-offset-4 cursor-pointer"
                              onClick={toggleExpand}
                            >
                              {storeText}
                            </button>
                          ) : (
                            <span className="text-green-500">{storeText}</span>
                          )
                        ) : null

                        const unavailable = !isOnline && !inStore

                        return (
                          <div className="flex flex-col gap-1 text-sm mt-1">
                            <div className="flex flex-wrap gap-x-1 gap-y-1">
                              {unavailable && hasSavedStores ? (
                                <span className="text-muted-foreground">
                                  Unavailable — you'll be notified
                                </span>
                              ) : (
                                <>
                                  {isOnline && (
                                    <span className="text-green-500">Available online</span>
                                  )}
                                  {isOnline && storeNode && (
                                    <span className="text-muted-foreground">·</span>
                                  )}
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
                      })()}
                    </>
                  ) : (
                    <p className="text-muted-foreground font-mono">
                      Product delisted (SKU: {watch.sku})
                    </p>
                  )}
                </div>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleRemove(watch.sku)}
                  disabled={removing === watch.sku}
                >
                  {removing === watch.sku ? 'Removing...' : 'Remove'}
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
