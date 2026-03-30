import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type { StoreWithDistance, UserStorePreferenceOut } from '@/lib/types'
import { Button } from '@/components/ui/button'

type GeoState =
  | { status: 'idle' }
  | { status: 'requesting' }
  | { status: 'granted'; lat: number; lng: number }
  | { status: 'denied'; errorCode: string }

function useGeolocation() {
  const [geo, setGeo] = useState<GeoState>({ status: 'idle' })

  const request = useCallback(() => {
    if (!navigator.geolocation) {
      setGeo({ status: 'denied', errorCode: 'notSupported' })
      return
    }

    setGeo({ status: 'requesting' })

    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGeo({
          status: 'granted',
          lat: position.coords.latitude,
          lng: position.coords.longitude,
        })
      },
      (error) => {
        const codes: Record<number, string> = {
          [GeolocationPositionError.PERMISSION_DENIED]: 'denied',
          [GeolocationPositionError.POSITION_UNAVAILABLE]: 'unavailable',
          [GeolocationPositionError.TIMEOUT]: 'timeout',
        }
        setGeo({ status: 'denied', errorCode: codes[error.code] ?? 'unknown' })
      },
      { enableHighAccuracy: false, timeout: 10_000 },
    )
  }, [])

  return { geo, request }
}

const GEO_ERROR_KEYS: Record<string, string> = {
  notSupported: 'editStores.geoNotSupported',
  denied: 'editStores.geoDenied',
  unavailable: 'editStores.geoUnavailable',
  timeout: 'editStores.geoTimeout',
}

function StoresPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const apiClient = useApiClient()
  const { geo, request: requestLocation } = useGeolocation()

  const [stores, setStores] = useState<StoreWithDistance[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())
  const [toggling, setToggling] = useState<string | null>(null)

  const lat = geo.status === 'granted' ? geo.lat : null
  const lng = geo.status === 'granted' ? geo.lng : null

  useEffect(() => {
    requestLocation()
  }, [requestLocation])

  // Fetch user's preferred stores on mount
  useEffect(() => {
    if (!user) return
    let cancelled = false

    async function fetchPreferences() {
      try {
        const prefs = await apiClient<UserStorePreferenceOut[]>('/stores/preferences')
        if (!cancelled) {
          setSavedIds(new Set(prefs.map((p) => p.saq_store_id)))
        }
      } catch {
        // Non-blocking — preferences just won't show as saved
      }
    }

    fetchPreferences()
    return () => {
      cancelled = true
    }
  }, [user, apiClient])

  // Fetch nearby stores when location is available
  useEffect(() => {
    if (lat === null || lng === null) return

    let cancelled = false
    setLoading(true)

    async function fetchStores() {
      try {
        const data = await apiClient<StoreWithDistance[]>(
          `/stores/nearby?lat=${lat}&lng=${lng}&limit=20`,
        )
        if (!cancelled) {
          setStores(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : t('editStores.failedToLoad'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchStores()

    return () => {
      cancelled = true
    }
  }, [lat, lng, apiClient, t])

  const handleToggle = useCallback(
    async (storeId: string) => {
      setToggling(storeId)
      const isSaved = savedIds.has(storeId)

      // Optimistic update
      setSavedIds((prev) => {
        const next = new Set(prev)
        if (isSaved) {
          next.delete(storeId)
        } else {
          next.add(storeId)
        }
        return next
      })

      try {
        if (isSaved) {
          await apiClient(`/stores/preferences/${storeId}`, { method: 'DELETE' })
        } else {
          await apiClient<UserStorePreferenceOut>('/stores/preferences', {
            method: 'POST',
            body: JSON.stringify({ saq_store_id: storeId }),
          })
        }
      } catch (err) {
        // Revert on failure
        setSavedIds((prev) => {
          const next = new Set(prev)
          if (isSaved) {
            next.add(storeId)
          } else {
            next.delete(storeId)
          }
          return next
        })
        setError(err instanceof ApiError ? err.detail : t('editStores.failedToUpdate'))
      } finally {
        setToggling(null)
      }
    },
    [apiClient, savedIds, t],
  )

  return (
    <div className="p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('editStores.title')}</h1>

        {error && <p className="text-destructive text-sm mb-4">{error}</p>}

        {(geo.status === 'idle' || geo.status === 'requesting') && (
          <p className="text-muted-foreground">{t('editStores.requestingLocation')}</p>
        )}

        {geo.status === 'denied' && (
          <div className="flex flex-col gap-4">
            <p className="text-muted-foreground">
              {t(GEO_ERROR_KEYS[geo.errorCode] ?? 'editStores.geoUnavailable')}
            </p>
            <div>
              <Button variant="outline" size="sm" onClick={requestLocation}>
                {t('editStores.tryAgain')}
              </Button>
            </div>
          </div>
        )}

        {loading && <p className="text-muted-foreground">{t('editStores.loading')}</p>}

        {geo.status === 'granted' && !loading && stores.length === 0 && !error && (
          <p className="text-muted-foreground">{t('editStores.noStores')}</p>
        )}

        {stores.length > 0 && (
          <ul className="flex flex-col gap-4">
            {stores.map((store) => {
              const isSaved = savedIds.has(store.saq_store_id)
              return (
                <li key={store.saq_store_id} className="border border-border p-4 rounded-lg">
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="font-bold truncate">{store.name}</p>
                      <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground mt-1">
                        {store.address && <span>{store.address}</span>}
                        <span>{store.city}</span>
                        {store.postcode && <span>{store.postcode}</span>}
                      </div>
                      {store.telephone && (
                        <p className="text-sm text-muted-foreground font-mono mt-1">{store.telephone}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-sm font-mono text-muted-foreground whitespace-nowrap">
                        {t('editStores.km', { distance: store.distance_km.toFixed(1) })}
                      </span>
                      <Button
                        variant={isSaved ? 'default' : 'outline'}
                        size="sm"
                        onClick={() => handleToggle(store.saq_store_id)}
                        disabled={toggling === store.saq_store_id}
                      >
                        {toggling === store.saq_store_id
                          ? '...'
                          : isSaved
                            ? t('editStores.saved')
                            : t('editStores.save')}
                      </Button>
                    </div>
                  </div>
                  {store.temporarily_closed && (
                    <p className="text-sm text-destructive mt-2">
                      {t('editStores.temporarilyClosed')}
                    </p>
                  )}
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}

export default StoresPage
