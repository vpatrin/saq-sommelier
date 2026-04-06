import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { Buildings, MapPin } from '@phosphor-icons/react'
import { useApiClient, ApiError } from '@/lib/api'
import type { UserStorePreferenceOut } from '@/lib/types'
import { Button } from '@/components/ui/button'
import EmptyState from '@/components/EmptyState'

function SavedStoresPage() {
  const { t } = useTranslation()
  const apiClient = useApiClient()
  const navigate = useNavigate()

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
          setError(err instanceof ApiError ? err.detail : t('stores.failedToLoad'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchPreferences()
    return () => {
      cancelled = true
    }
  }, [apiClient, t])

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mx-auto flex max-w-2xl flex-col gap-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="border-border h-[72px] animate-pulse rounded-xl border bg-white/[0.025]"
            />
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="mx-auto max-w-2xl">
        <div className="mb-6 flex items-baseline justify-between">
          <div className="flex items-baseline gap-2.5">
            <h1 className="text-2xl font-light">{t('stores.title')}</h1>
            {preferences.length > 0 && (
              <span className="text-muted-foreground/60 font-mono text-[11px] tabular-nums">
                {preferences.length}
              </span>
            )}
          </div>
          <Link to="/stores/nearby">
            <Button variant="outline" size="sm">
              {t('stores.edit')}
            </Button>
          </Link>
        </div>

        {error && <p className="text-destructive mb-4 text-[13px]">{error}</p>}

        {preferences.length === 0 ? (
          <EmptyState
            icon={<Buildings size={28} />}
            title={t('stores.emptyTitle')}
            description={t('stores.emptyDesc')}
            cta={{ label: t('stores.emptyCta'), onClick: () => navigate('/stores/nearby') }}
          />
        ) : (
          <ul className="flex flex-col gap-2">
            {preferences.map(({ saq_store_id, store }) => {
              const addressLine = [store.address, store.city, store.postcode]
                .filter(Boolean)
                .join(', ')

              return (
                <li
                  key={saq_store_id}
                  className="border-border hover:border-primary/20 relative overflow-hidden rounded-xl border bg-white/[0.025] px-[18px] py-3.5 transition-colors"
                >
                  {/* Warm gradient overlay */}
                  <div className="from-primary/[0.02] pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br to-transparent" />

                  <div className="relative flex items-center gap-3">
                    <MapPin
                      size={13}
                      weight="fill"
                      className="text-muted-foreground/30 flex-shrink-0"
                    />
                    <div className="min-w-0">
                      <p className="truncate text-[14px] leading-snug font-medium">{store.name}</p>
                      {addressLine && (
                        <p className="text-muted-foreground/60 mt-0.5 truncate text-[11px] leading-snug">
                          {addressLine}
                        </p>
                      )}
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

export default SavedStoresPage
