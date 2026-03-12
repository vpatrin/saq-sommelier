import { useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useApiClient, ApiError } from '@/lib/api'
import type { UserStorePreferenceOut } from '@/lib/types'
import { Button } from '@/components/ui/button'

function SavedStoresPage() {
  const apiClient = useApiClient()

  const [preferences, setPreferences] = useState<UserStorePreferenceOut[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function fetchPreferences() {
      try {
        const data = await apiClient<UserStorePreferenceOut[]>('/stores/preferences')
        if (!cancelled) {
          setPreferences(data)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : 'Failed to load saved stores')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchPreferences()
    return () => { cancelled = true }
  }, [apiClient])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-muted-foreground font-mono">Loading saved stores...</p>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="max-w-2xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-mono font-bold">My Stores</h1>
          <Link to="/stores/nearby">
            <Button variant="outline" size="sm">Edit</Button>
          </Link>
        </div>

        {error && (
          <p className="text-destructive text-sm font-mono mb-4">{error}</p>
        )}

        {preferences.length === 0 ? (
          <p className="text-muted-foreground font-mono">
            No saved stores yet. Tap Edit to find nearby stores.
          </p>
        ) : (
          <ul className="flex flex-col gap-4">
            {preferences.map(({ saq_store_id, store }) => (
              <li
                key={saq_store_id}
                className="border border-border p-4"
              >
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
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

export default SavedStoresPage
