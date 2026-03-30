import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { useSearchParams } from 'react-router'
import { useTranslation } from 'react-i18next'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import type {
  PaginatedOut,
  FacetsOut,
  CategoryGroupOut,
  WatchWithProduct,
  UserStorePreferenceOut,
} from '@/lib/types'
import { Button } from '@/components/ui/button'
import WineCard from '@/components/WineCard'

const DEBOUNCE_MS = 300
const LIMIT = 20
const GROUP_PREFIX = 'group:'

/** Resolve a category URL param to API query params. */
function resolveCategories(value: string, groups: CategoryGroupOut[]): string[] {
  if (!value) return []
  if (!value.startsWith(GROUP_PREFIX)) return [value]
  const key = value.slice(GROUP_PREFIX.length)
  const group = groups.find((g) => g.key === key)
  return group ? group.categories : []
}

/** Get the active group key from the current category param. */
function activeGroupKey(category: string, groups: CategoryGroupOut[]): string | null {
  if (!category) return null
  if (category.startsWith(GROUP_PREFIX)) return category.slice(GROUP_PREFIX.length)
  // Raw category name — find which group owns it
  const parent = groups.find((g) => g.categories.includes(category))
  return parent?.key ?? null
}

function SearchPage() {
  const { t } = useTranslation()
  const { user } = useAuth()
  const apiClient = useApiClient()
  const [searchParams, setSearchParams] = useSearchParams()

  // Filters from URL params (source of truth)
  const query = searchParams.get('q') ?? ''
  const country = searchParams.get('country') ?? ''
  const category = searchParams.get('category') ?? ''
  const sort = searchParams.get('sort') ?? 'recent'
  const onlineOnly = searchParams.get('online') === '1'
  const inStoresOnly = searchParams.get('in_stores') === '1'
  const minPrice = searchParams.get('min_price') ?? ''
  const maxPrice = searchParams.get('max_price') ?? ''
  const page = Number(searchParams.get('page') ?? '1')

  // Local input for debounced search
  const [inputValue, setInputValue] = useState(query)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Sync input when URL query changes externally (browser back/forward)
  useEffect(() => {
    setInputValue(query)
  }, [query])

  // Clean up pending debounce on unmount
  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  // Data state
  const [results, setResults] = useState<PaginatedOut | null>(null)
  const [facets, setFacets] = useState<FacetsOut | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)

  // Watch state — track which SKUs the user is already watching
  const [watchedSkus, setWatchedSkus] = useState<Set<string>>(new Set())
  const [watchingInProgress, setWatchingInProgress] = useState<string | null>(null)
  const [expandedStores, setExpandedStores] = useState<Set<string>>(new Set())
  const toggleStoreExpand = useCallback((sku: string) => {
    setExpandedStores((prev) => {
      const next = new Set(prev)
      if (next.has(sku)) next.delete(sku)
      else next.add(sku)
      return next
    })
  }, [])

  // Saved store IDs + names — for "In my stores" filter and availability display
  const [savedStoreIdsRaw, setSavedStoreIds] = useState<string[]>([])
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const [storesLoaded, setStoresLoaded] = useState(false)
  // Stable reference: only changes when the actual IDs change, not on every render
  const storeIdsKey = savedStoreIdsRaw.join(',')
  const savedStoreIds = useMemo(() => savedStoreIdsRaw, [storeIdsKey])

  // Stable ref for grouped categories — avoids circular dependency in facets effect
  // (effect reads groups to resolve category param, then sets facets which contains groups)
  const groupsRef = useRef<CategoryGroupOut[]>([])

  const userId = `tg:${user?.telegram_id}`

  // Shared: append category, availability, and store filters to params
  const appendFilterParams = useCallback(
    (params: URLSearchParams) => {
      for (const cat of resolveCategories(category, groupsRef.current)) {
        params.append('category', cat)
      }
      if (onlineOnly) params.set('available', 'true')
      if (inStoresOnly && savedStoreIds.length > 0) {
        for (const id of savedStoreIds) {
          params.append('in_stores', id)
        }
      }
    },
    [category, onlineOnly, inStoresOnly, savedStoreIds],
  )

  // Fetch facets — re-fetches when category or availability filters change
  // so country counts reflect the active filter set.
  // Wait for store prefs before fetching if "In my stores" is active.
  useEffect(() => {
    if (inStoresOnly && !storesLoaded) return
    let cancelled = false
    async function fetchFacets() {
      const params = new URLSearchParams()
      appendFilterParams(params)
      const qs = params.toString()
      try {
        const data = await apiClient<FacetsOut>(`/products/facets${qs ? `?${qs}` : ''}`)
        if (!cancelled) {
          groupsRef.current = data.grouped_categories
          setFacets(data)
        }
      } catch {
        // Non-critical — filters degrade gracefully without facets
      }
    }
    fetchFacets()
    return () => {
      cancelled = true
    }
  }, [apiClient, appendFilterParams, inStoresOnly, storesLoaded])

  // Fetch existing watches and saved stores on mount
  useEffect(() => {
    let cancelled = false

    async function fetchWatches() {
      try {
        const data = await apiClient<WatchWithProduct[]>(
          `/watches?user_id=${encodeURIComponent(userId)}`,
        )
        if (!cancelled) {
          setWatchedSkus(new Set(data.map((w) => w.watch.sku)))
        }
      } catch {
        // Non-critical — watch buttons default to "Watch"
      }
    }

    async function fetchStorePrefs() {
      try {
        const prefs = await apiClient<UserStorePreferenceOut[]>('/stores/preferences')
        if (!cancelled) {
          setSavedStoreIds(prefs.map((p) => p.saq_store_id).sort())
          setStoreNames(new Map(prefs.map((p) => [p.saq_store_id, p.store.name])))
        }
      } catch {
        // Non-critical — "In my stores" filter won't work without prefs
      } finally {
        if (!cancelled) setStoresLoaded(true)
      }
    }

    fetchWatches()
    fetchStorePrefs()
    return () => {
      cancelled = true
    }
  }, [apiClient, userId])

  // Fetch products whenever URL params change.
  // Wait for store prefs before fetching if "In my stores" is active.
  useEffect(() => {
    if (inStoresOnly && !storesLoaded) return
    let cancelled = false

    async function fetchProducts() {
      setLoading(true)
      setError(null)

      const params = new URLSearchParams()
      params.set('limit', String(LIMIT))
      params.set('offset', String((page - 1) * LIMIT))
      if (query) params.set('q', query)
      if (country) params.set('country', country)
      appendFilterParams(params)
      if (sort) params.set('sort', sort)
      if (minPrice) params.set('min_price', minPrice)
      if (maxPrice) params.set('max_price', maxPrice)

      try {
        const data = await apiClient<PaginatedOut>(`/products?${params}`)
        if (!cancelled) setResults(data)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.detail : t('search.failedToSearch'))
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchProducts()
    return () => {
      cancelled = true
    }
  }, [
    apiClient,
    query,
    country,
    appendFilterParams,
    sort,
    minPrice,
    maxPrice,
    page,
    retryCount,
    inStoresOnly,
    storesLoaded,
    t,
  ])

  // Debounced search input
  const handleInputChange = useCallback(
    (value: string) => {
      setInputValue(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev)
          if (value) {
            next.set('q', value)
          } else {
            next.delete('q')
          }
          next.delete('page') // Reset to page 1 on new search
          return next
        })
      }, DEBOUNCE_MS)
    },
    [setSearchParams],
  )

  // Filter change helpers — reset page on any filter change
  const setFilter = useCallback(
    (key: string, value: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (value) {
          next.set(key, value)
        } else {
          next.delete(key)
        }
        next.delete('page')
        return next
      })
    },
    [setSearchParams],
  )

  const toggleFilter = useCallback(
    (key: string) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (next.get(key) === '1') {
          next.delete(key)
        } else {
          next.set(key, '1')
        }
        next.delete('page')
        return next
      })
    },
    [setSearchParams],
  )

  const setPage = useCallback(
    (p: number) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev)
        if (p > 1) {
          next.set('page', String(p))
        } else {
          next.delete('page')
        }
        return next
      })
    },
    [setSearchParams],
  )

  const handleWatch = useCallback(
    async (sku: string) => {
      setWatchingInProgress(sku)
      // Optimistic update
      setWatchedSkus((prev) => new Set([...prev, sku]))
      try {
        await apiClient('/watches', {
          method: 'POST',
          body: JSON.stringify({ sku }),
        })
      } catch (err) {
        // Rollback on failure
        setWatchedSkus((prev) => {
          const next = new Set(prev)
          next.delete(sku)
          return next
        })
        setError(err instanceof ApiError ? err.detail : t('search.failedToAddWatch'))
      } finally {
        setWatchingInProgress(null)
      }
    },
    [apiClient, t],
  )

  const handleUnwatch = useCallback(
    async (sku: string) => {
      setWatchingInProgress(sku)
      // Optimistic update
      setWatchedSkus((prev) => {
        const next = new Set(prev)
        next.delete(sku)
        return next
      })
      try {
        await apiClient(`/watches/${sku}?user_id=${encodeURIComponent(userId)}`, {
          method: 'DELETE',
        })
      } catch (err) {
        // Rollback on failure
        setWatchedSkus((prev) => new Set([...prev, sku]))
        setError(err instanceof ApiError ? err.detail : t('search.failedToRemoveWatch'))
      } finally {
        setWatchingInProgress(null)
      }
    },
    [apiClient, userId, t],
  )

  const displayProducts = results?.products ?? []
  const pages = results ? Math.ceil(results.total / results.limit) : 0
  const hasStores = storeNames.size > 0

  return (
    <div className="p-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('search.title')}</h1>

        {/* Search input */}
        <input
          type="text"
          value={inputValue}
          onChange={(e) => handleInputChange(e.target.value)}
          placeholder={t('search.placeholder')}
          aria-label={t('search.placeholder')}
          className="w-full bg-background border border-border rounded-lg px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:border-ring mb-4"
        />

        {/* Category chips — top level (groups) */}
        {facets && (
          <div className="flex flex-col gap-2 mb-4">
            <div className="flex flex-wrap gap-1.5">
              {facets.category_families.map((family, fi) => (
                <span key={family.key} className="contents">
                  {fi > 0 && <span className="w-px bg-border self-stretch mx-1" />}
                  {family.children.map((groupKey) => {
                    const group = facets.grouped_categories.find((g) => g.key === groupKey)
                    if (!group) return null
                    const isActive =
                      category === `${GROUP_PREFIX}${groupKey}` ||
                      (!category.startsWith(GROUP_PREFIX) &&
                        category !== '' &&
                        group.categories.includes(category))
                    return (
                      <button
                        key={groupKey}
                        type="button"
                        onClick={() =>
                          setFilter('category', isActive ? '' : `${GROUP_PREFIX}${groupKey}`)
                        }
                        className={`border rounded-full px-2 py-1 text-xs transition-colors ${
                          isActive
                            ? 'border-primary bg-primary/10 text-primary'
                            : 'border-border text-muted-foreground hover:text-foreground'
                        }`}
                      >
                        {group.label}
                      </button>
                    )
                  })}
                </span>
              ))}
            </div>

            {/* Sub-categories — chips for small groups, dropdown for large ones */}
            {(() => {
              const groupKey = activeGroupKey(category, facets.grouped_categories)
              if (!groupKey) return null
              const group = facets.grouped_categories.find((g) => g.key === groupKey)
              if (!group || group.categories.length < 2) return null

              // Large groups: "All" chip + dropdown to narrow
              if (group.categories.length > 5) {
                const isAllActive = category === `${GROUP_PREFIX}${groupKey}`
                return (
                  <div className="flex flex-wrap items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setFilter('category', `${GROUP_PREFIX}${groupKey}`)}
                      className={`border rounded-full px-2 py-1 text-xs transition-colors ${
                        isAllActive
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {t('search.all')}
                    </button>
                    <select
                      value={category.startsWith(GROUP_PREFIX) ? '' : category}
                      onChange={(e) =>
                        setFilter('category', e.target.value || `${GROUP_PREFIX}${groupKey}`)
                      }
                      className="bg-background border border-border rounded-lg px-2 py-1 text-xs focus:outline-none focus:border-ring"
                    >
                      <option value="">{t('search.narrow')}</option>
                      {group.categories.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </div>
                )
              }

              return (
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setFilter('category', `${GROUP_PREFIX}${groupKey}`)}
                    className={`border rounded-full px-2 py-1 text-xs transition-colors ${
                      category === `${GROUP_PREFIX}${groupKey}`
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    All
                  </button>
                  {group.categories.map((cat) => (
                    <button
                      key={cat}
                      type="button"
                      onClick={() => setFilter('category', cat)}
                      className={`border rounded-full px-2 py-1 text-xs transition-colors ${
                        category === cat
                          ? 'border-primary bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground hover:text-foreground'
                      }`}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              )
            })()}
          </div>
        )}

        <hr className="border-border mb-4" />

        {/* Two-column layout: filters sidebar + results */}
        <div className="flex gap-6">
          {/* Filters sidebar */}
          <aside className="w-44 shrink-0 flex flex-col gap-4">
            <div>
              <p className="text-xs text-muted-foreground mb-2">{t('search.country')}</p>
              <select
                value={country}
                onChange={(e) => setFilter('country', e.target.value)}
                className="w-full bg-background border border-border rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-ring"
              >
                <option value="">{t('search.all')}</option>
                {facets?.countries.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name} ({c.count})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <p className="text-xs text-muted-foreground mb-2">
                {t('search.availability')}
              </p>
              <div className="flex flex-col gap-1.5">
                <button
                  type="button"
                  onClick={() => toggleFilter('online')}
                  className={`border rounded-lg px-2 py-1.5 text-xs text-left transition-colors ${
                    onlineOnly
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {t('search.availableOnline')}
                </button>

                <button
                  type="button"
                  onClick={() => toggleFilter('in_stores')}
                  disabled={savedStoreIds.length === 0}
                  className={`border rounded-lg px-2 py-1.5 text-xs text-left transition-colors ${
                    savedStoreIds.length === 0
                      ? 'border-border text-muted-foreground/50 cursor-not-allowed'
                      : inStoresOnly
                        ? 'border-primary bg-primary/10 text-primary'
                        : 'border-border text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {savedStoreIds.length > 0 ? t('search.inMyStores') : t('search.inMyStoresNone')}
                </button>
              </div>
            </div>

            <div>
              <p className="text-xs text-muted-foreground mb-2">{t('search.price')}</p>
              <div className="flex gap-2">
                <input
                  key={`min-${minPrice}`}
                  type="number"
                  min="0"
                  step="1"
                  placeholder={facets?.price_range?.min ?? '0'}
                  defaultValue={minPrice}
                  onBlur={(e) => setFilter('min_price', e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                  }}
                  aria-label={t('search.minPrice')}
                  className="w-full bg-background border border-border rounded-lg px-2 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:border-ring"
                />
                <input
                  key={`max-${maxPrice}`}
                  type="number"
                  min="0"
                  step="1"
                  placeholder={facets?.price_range?.max ?? '∞'}
                  defaultValue={maxPrice}
                  onBlur={(e) => setFilter('max_price', e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
                  }}
                  aria-label={t('search.maxPrice')}
                  className="w-full bg-background border border-border rounded-lg px-2 py-1.5 text-xs placeholder:text-muted-foreground focus:outline-none focus:border-ring"
                />
              </div>
            </div>
          </aside>

          {/* Results */}
          <div className="flex-1 min-w-0">
            {/* Error */}
            {error && (
              <p className="text-destructive text-sm mb-4">
                {error}
                {' — '}
                <button
                  type="button"
                  onClick={() => setRetryCount((c) => c + 1)}
                  className="underline hover:text-destructive/80"
                >
                  {t('search.retry')}
                </button>
              </p>
            )}

            {loading ? (
              <p className="text-muted-foreground">{t('search.loading')}</p>
            ) : results && displayProducts.length > 0 ? (
              <>
                <div className="flex items-center justify-between mb-4">
                  <p className="text-xs text-muted-foreground font-mono">
                    {t('search.result', { count: results.total })}
                    {pages > 1 && ` · ${t('search.pageOf', { page, pages })}`}
                  </p>
                  <select
                    value={sort}
                    onChange={(e) => setFilter('sort', e.target.value)}
                    className="bg-background border border-border rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:border-ring"
                  >
                    <option value="recent">{t('search.sortRecent')}</option>
                    <option value="price_asc">{t('search.sortPriceAsc')}</option>
                    <option value="price_desc">{t('search.sortPriceDesc')}</option>
                    <option value="alpha">{t('search.sortAlpha')}</option>
                  </select>
                </div>

                <ul className="flex flex-col gap-3">
                  {displayProducts.map((product) => {
                    const isWatched = watchedSkus.has(product.sku)
                    const isBusy = watchingInProgress === product.sku
                    const isOnline = product.online_availability === true
                    const storeAvail = product.store_availability ?? []
                    const matchingIds = storeAvail.filter((id) => storeNames.has(id))
                    const hasAvailability =
                      isOnline ||
                      (hasStores && matchingIds.length > 0) ||
                      (!hasStores && storeAvail.length > 0)
                    return (
                      <li
                        key={product.sku}
                        className={`border border-border rounded-lg p-4 flex justify-between items-start gap-4${hasAvailability ? '' : ' opacity-50'}`}
                      >
                        <WineCard
                          product={product}
                          storeNames={storeNames}
                          storesExpanded={expandedStores.has(product.sku)}
                          onToggleStores={() => toggleStoreExpand(product.sku)}
                        />

                        <button
                          type="button"
                          disabled={isBusy}
                          onClick={() =>
                            isWatched ? handleUnwatch(product.sku) : handleWatch(product.sku)
                          }
                          className={`border rounded-lg px-3 py-1.5 text-xs transition-colors shrink-0 ${
                            isWatched
                              ? 'border-primary bg-primary/10 text-primary'
                              : 'border-border text-muted-foreground hover:text-foreground'
                          } ${isBusy ? 'opacity-50' : ''}`}
                        >
                          {isBusy ? '...' : isWatched ? t('search.watching') : t('search.watch')}
                        </button>
                      </li>
                    )
                  })}
                </ul>

                {/* Pagination */}
                {pages > 1 && (
                  <div className="flex items-center gap-2 mt-6 font-mono text-sm">
                    <Button
                      variant="outline"
                      size="xs"
                      disabled={page <= 1}
                      onClick={() => setPage(1)}
                    >
                      {t('search.first')}
                    </Button>
                    <Button
                      variant="outline"
                      size="xs"
                      disabled={page <= 1}
                      onClick={() => setPage(page - 1)}
                    >
                      {t('search.prev')}
                    </Button>
                    {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
                      let p: number
                      if (pages <= 7) {
                        p = i + 1
                      } else if (page <= 4) {
                        p = i + 1
                      } else if (page >= pages - 3) {
                        p = pages - 6 + i
                      } else {
                        p = page - 3 + i
                      }
                      return (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setPage(p)}
                          className={`px-2 py-1 text-xs ${
                            p === page ? 'bg-primary text-primary-foreground' : 'hover:bg-muted'
                          }`}
                        >
                          {p}
                        </button>
                      )
                    })}
                    <Button
                      variant="outline"
                      size="xs"
                      disabled={page >= pages}
                      onClick={() => setPage(page + 1)}
                    >
                      {t('search.next')}
                    </Button>
                    <Button
                      variant="outline"
                      size="xs"
                      disabled={page >= pages}
                      onClick={() => setPage(pages)}
                    >
                      {t('search.last')}
                    </Button>
                  </div>
                )}
              </>
            ) : (
              <p className="text-muted-foreground">{t('search.noResults')}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default SearchPage
