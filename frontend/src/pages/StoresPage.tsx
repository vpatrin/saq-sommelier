import { useEffect, useState, useCallback } from 'react'
import { useApiClient, ApiError } from '@/lib/api'
import type { StoreWithDistance } from '@/lib/types'
import { Button } from '@/components/ui/button'

type GeoState =
  | { status: 'idle' }
  | { status: 'requesting' }
  | { status: 'granted'; lat: number; lng: number }
  | { status: 'denied'; message: string }

function useGeolocation() {
  const [geo, setGeo] = useState<GeoState>({ status: 'idle' })

  const request = useCallback(() => {
    if (!navigator.geolocation) {
      setGeo({ status: 'denied', message: 'Geolocation is not supported by your browser.' })
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
        const messages: Record<number, string> = {
          [GeolocationPositionError.PERMISSION_DENIED]:
            'Location permission denied. Enable it in your browser settings to see nearby stores.',
          [GeolocationPositionError.POSITION_UNAVAILABLE]:
            'Unable to determine your location.',
          [GeolocationPositionError.TIMEOUT]:
            'Location request timed out. Try again.',
        }
        setGeo({ status: 'denied', message: messages[error.code] ?? 'Unknown location error.' })
      },
      { enableHighAccuracy: false, timeout: 10_000 }
    )
  }, [])

  return { geo, request }
}

function StoresPage() {
  const apiClient = useApiClient()
  const { geo, request: requestLocation } = useGeolocation()

  const [stores, setStores] = useState<StoreWithDistance[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const lat = geo.status === 'granted' ? geo.lat : null
  const lng = geo.status === 'granted' ? geo.lng : null

  useEffect(() => {
    requestLocation()
  }, [requestLocation])

  useEffect(() => {
    if (lat === null || lng === null) return

    let cancelled = false
    setLoading(true)

    async function fetchStores() {
      try {
        const data = await apiClient<StoreWithDistance[]>(
          `/stores/nearby?lat=${lat}&lng=${lng}&limit=20`
        )
        if (!cancelled) {
          setStores(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : 'Failed to load stores')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchStores()

    return () => {
      cancelled = true
    }
  }, [lat, lng, apiClient])

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-mono font-bold mb-6">Nearby Stores</h1>

        {error && (
          <p className="text-destructive text-sm font-mono mb-4">{error}</p>
        )}

        {(geo.status === 'idle' || geo.status === 'requesting') && (
          <p className="text-muted-foreground font-mono">
            Requesting your location...
          </p>
        )}

        {geo.status === 'denied' && (
          <div className="flex flex-col gap-4">
            <p className="text-muted-foreground font-mono">{geo.message}</p>
            <div>
              <Button variant="outline" size="sm" onClick={requestLocation}>
                Try again
              </Button>
            </div>
          </div>
        )}

        {loading && (
          <p className="text-muted-foreground font-mono">Loading stores...</p>
        )}

        {geo.status === 'granted' && !loading && stores.length === 0 && !error && (
          <p className="text-muted-foreground font-mono">
            No stores found nearby.
          </p>
        )}

        {stores.length > 0 && (
          <ul className="flex flex-col gap-4">
            {stores.map((store) => (
              <li
                key={store.saq_store_id}
                className="border border-border p-4"
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="font-mono font-bold truncate">
                      {store.name}
                    </p>
                    <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground mt-1">
                      {store.address && <span>{store.address}</span>}
                      <span>{store.city}</span>
                      {store.postcode && <span>{store.postcode}</span>}
                    </div>
                    {store.telephone && (
                      <p className="text-sm text-muted-foreground mt-1">
                        {store.telephone}
                      </p>
                    )}
                  </div>
                  <span className="text-sm font-mono text-muted-foreground whitespace-nowrap">
                    {store.distance_km.toFixed(1)} km
                  </span>
                </div>
                {store.temporarily_closed && (
                  <p className="text-sm text-destructive mt-2 font-mono">
                    Temporarily closed
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default StoresPage
