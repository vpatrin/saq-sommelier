import { useEffect, useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type { StoreWithDistance, UserStorePreferenceOut } from '@/lib/types'
import { Button } from '@/components/ui/button'
import {
  MapPinIcon as MapPin,
  BuildingsIcon as Buildings,
  ArrowLeftIcon as ArrowLeft,
} from '@phosphor-icons/react'
import EmptyState from '@/components/EmptyState'

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
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-6">
          <Link
            to="/stores"
            className="text-muted-foreground/50 hover:text-foreground transition-colors"
            aria-label={t('login.backToLanding')}
          >
            <ArrowLeft size={18} />
          </Link>
          <h1 className="text-2xl font-light">{t('editStores.title')}</h1>
        </div>

        {error && <p className="text-destructive text-[13px] mb-4">{error}</p>}

        {/* Geolocation states */}
        {(geo.status === 'idle' || geo.status === 'requesting') && (
          <div className="flex items-start gap-3 rounded-xl border border-green-500/20 bg-green-500/[0.06] px-4 py-3.5 mb-6">
            <MapPin size={16} weight="fill" className="text-green-500 mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-green-400/90 leading-snug">
                {t('editStores.requestingLocation')}
              </p>
            </div>
          </div>
        )}

        {geo.status === 'denied' && (
          <div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/[0.06] px-4 py-3.5 mb-6">
            <MapPin size={16} weight="fill" className="text-destructive mt-0.5 flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-[13px] text-destructive/80 leading-snug mb-2.5">
                {t(GEO_ERROR_KEYS[geo.errorCode] ?? 'editStores.geoUnavailable')}
              </p>
              {geo.errorCode !== 'denied' && (
                <Button variant="outline" size="sm" onClick={requestLocation}>
                  {t('editStores.tryAgain')}
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && (
          <div className="flex flex-col gap-3">
            {[...Array(3)].map((_, i) => (
              <div
                key={i}
                className="h-[76px] rounded-xl bg-white/[0.025] border border-border animate-pulse"
              />
            ))}
          </div>
        )}

        {/* Empty: location granted but no stores */}
        {geo.status === 'granted' && !loading && stores.length === 0 && !error && (
          <EmptyState icon={<Buildings size={28} />} title={t('editStores.noStores')} />
        )}

        {stores.length > 0 && (
          <ul className="flex flex-col gap-2">
            {stores.map((store) => {
              const isSaved = savedIds.has(store.saq_store_id)
              const addressLine = [store.address, store.city, store.postcode]
                .filter(Boolean)
                .join(', ')

              return (
                <li
                  key={store.saq_store_id}
                  className="relative overflow-hidden rounded-xl border border-border bg-white/[0.025] transition-colors hover:border-primary/20 px-[18px] py-3.5"
                >
                  {/* Warm gradient overlay */}
                  <div className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br from-primary/[0.02] to-transparent" />

                  <div className="relative flex items-center justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <p className="text-[14px] font-medium leading-snug truncate">{store.name}</p>
                      {addressLine && (
                        <p className="text-[11px] text-muted-foreground/60 mt-0.5 leading-snug truncate">
                          {addressLine}
                        </p>
                      )}
                      {store.temporarily_closed && (
                        <p className="text-[10px] text-destructive/70 mt-0.5">
                          {t('editStores.temporarilyClosed')}
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className="font-mono text-[11px] text-muted-foreground/50 whitespace-nowrap">
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
