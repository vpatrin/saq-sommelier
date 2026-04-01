import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router'
import { useTranslation } from 'react-i18next'
import { MagnifyingGlassIcon as MagnifyingGlass, WineIcon as Wine } from '@phosphor-icons/react'
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
import { CATEGORY_DOT } from '@/lib/utils'
import WineCard from '@/components/WineCard'
import EmptyState from '@/components/EmptyState'
import { useWineDetail } from '@/contexts/WineDetailContext'

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
  const navigate = useNavigate()
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

  const { selectedSku, setSelectedSku } = useWineDetail()

  // Watch state — track which SKUs the user is already watching
  const [watchedSkus, setWatchedSkus] = useState<Set<string>>(new Set())
  const [watchingInProgress, setWatchingInProgress] = useState<string | null>(null)

  // Saved store IDs + names — for "In my stores" filter and availability display
  const [savedStoreIdsRaw, setSavedStoreIds] = useState<string[]>([])
  const [storeNames, setStoreNames] = useState<Map<string, string>>(new Map())
  const [storesLoaded, setStoresLoaded] = useState(false)
  // Stable reference: only changes when the actual IDs change, not on every render
  const storeIdsKey = savedStoreIdsRaw.join(',')
  // eslint-disable-next-line react-hooks/exhaustive-deps
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

  const resetFilters = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams()
      // Keep the search query only
      const q = prev.get('q')
      if (q) next.set('q', q)
      return next
    })
  }, [setSearchParams])

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

  // Category chips built from facet groups
  const categoryChips = facets
    ? facets.category_families.flatMap((family) =>
        family.children.flatMap((groupKey) => {
          const group = facets.grouped_categories.find((g) => g.key === groupKey)
          if (!group) return []
          const dotColor = CATEGORY_DOT[group.categories[0]] ?? 'bg-muted-foreground/30'
          return [{ label: group.label, value: `${GROUP_PREFIX}${groupKey}`, dotColor }]
        }),
      )
    : []

  // Active category chip value (normalize raw category → group prefix form)
  const activeCategoryChip = (() => {
    if (!category || !facets) return ''
    if (category.startsWith(GROUP_PREFIX)) return category
    const parent = facets.grouped_categories.find((g) => g.categories.includes(category))
    return parent ? `${GROUP_PREFIX}${parent.key}` : ''
  })()

  // Active sub-category group (shown as secondary chips or dropdown)
  const activeSubGroup = facets
    ? facets.grouped_categories.find(
        (g) => g.key === activeGroupKey(category, facets.grouped_categories),
      )
    : null

  // Any secondary filter is active (not counting category chips)
  const hasSecondaryFilters = !!(country || onlineOnly || inStoresOnly || minPrice || maxPrice)

  return (
    <div className="flex-1 relative overflow-hidden">
      <div
        className={`h-full overflow-y-auto p-8 transition-[padding-right] duration-300 ease-out ${selectedSku ? 'pr-[376px]' : ''}`}
      >
        <div className="max-w-2xl mx-auto">
          <h1 className="text-2xl font-light mb-6">{t('search.title')}</h1>

          {/* Search input */}
          <div className="relative mb-4">
            <MagnifyingGlass
              size={15}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
            />
            <input
              type="text"
              value={inputValue}
              onChange={(e) => handleInputChange(e.target.value)}
              placeholder={t('search.placeholder')}
              aria-label={t('search.placeholder')}
              className="w-full h-10 pl-9 pr-4 rounded-xl bg-white/[0.04] border border-border text-[14px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors"
            />
          </div>

          {/* Category chips */}
          {categoryChips.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {categoryChips.map((chip) => (
                <button
                  key={chip.value}
                  type="button"
                  onClick={() =>
                    setFilter('category', activeCategoryChip === chip.value ? '' : chip.value)
                  }
                  className={`flex items-center gap-1.5 border rounded-full px-3 py-1 text-[12px] whitespace-nowrap transition-colors ${
                    activeCategoryChip === chip.value
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80'
                  }`}
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${chip.dotColor}`} />
                  {chip.label}
                </button>
              ))}
            </div>
          )}

          {/* Sub-category chips */}
          {activeSubGroup && activeSubGroup.categories.length >= 2 && (
            <div className="flex flex-wrap gap-1.5 mb-4">
              <button
                type="button"
                onClick={() => setFilter('category', `${GROUP_PREFIX}${activeSubGroup.key}`)}
                className={`border rounded-full px-3 py-1 text-[12px] whitespace-nowrap transition-colors ${
                  category === `${GROUP_PREFIX}${activeSubGroup.key}`
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80'
                }`}
              >
                {t('search.all')}
              </button>
              {activeSubGroup.categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFilter('category', cat)}
                  className={`border rounded-full px-3 py-1 text-[12px] whitespace-nowrap transition-colors ${
                    category === cat
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:text-foreground hover:border-border/80'
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}

          {/* Error */}
          {error && (
            <p className="text-destructive text-[13px] mb-4">
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

          {/* Inline filter bar */}
          <div className="flex items-center gap-2 mb-4">
            <select
              value={country}
              onChange={(e) => setFilter('country', e.target.value)}
              className={`w-44 bg-white/[0.04] border rounded-lg px-2.5 py-1.5 text-[12px] focus:outline-none focus:border-primary/30 transition-colors ${
                country ? 'border-primary/40 text-primary' : 'border-border text-muted-foreground'
              }`}
            >
              <option value="">{t('search.country')}</option>
              {facets?.countries.map((c) => (
                <option key={c.name} value={c.name}>
                  {c.name} ({c.count})
                </option>
              ))}
            </select>

            <input
              type="number"
              min="0"
              step="1"
              placeholder="0"
              defaultValue={minPrice}
              onBlur={(e) => setFilter('min_price', e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
              }}
              aria-label={t('search.minPrice')}
              className={`w-20 bg-white/[0.04] border rounded-lg px-2.5 py-1.5 text-[12px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors ${
                minPrice ? 'border-primary/40' : 'border-border'
              }`}
            />
            <span className="text-[11px] text-muted-foreground/50">–</span>
            <input
              type="number"
              min="0"
              step="1"
              placeholder="∞"
              defaultValue={maxPrice}
              onBlur={(e) => setFilter('max_price', e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
              }}
              aria-label={t('search.maxPrice')}
              className={`w-20 bg-white/[0.04] border rounded-lg px-2.5 py-1.5 text-[12px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors ${
                maxPrice ? 'border-primary/40' : 'border-border'
              }`}
            />

            <button
              type="button"
              onClick={() => setFilter('online', onlineOnly ? '' : '1')}
              className={`border rounded-lg px-2.5 py-1.5 text-[12px] transition-colors ${
                onlineOnly
                  ? 'border-primary/40 bg-primary/10 text-primary'
                  : 'border-border text-muted-foreground hover:text-foreground'
              }`}
            >
              {t('search.availableOnline')}
            </button>

            {savedStoreIds.length > 0 && (
              <button
                type="button"
                onClick={() => setFilter('in_stores', inStoresOnly ? '' : '1')}
                className={`border rounded-lg px-2.5 py-1.5 text-[12px] transition-colors ${
                  inStoresOnly
                    ? 'border-primary/40 bg-primary/10 text-primary'
                    : 'border-border text-muted-foreground hover:text-foreground'
                }`}
              >
                {t('search.inMyStores')}
              </button>
            )}

            <button
              type="button"
              onClick={resetFilters}
              disabled={!hasSecondaryFilters && !category}
              className="border rounded-lg px-2.5 py-1.5 text-[12px] border-border text-muted-foreground/40 disabled:opacity-30 hover:text-foreground hover:border-border/80 transition-colors"
            >
              {t('search.reset')}
            </button>
          </div>

          {loading ? (
            <div className="grid grid-cols-2 gap-2">
              {[...Array(6)].map((_, i) => (
                <div
                  key={i}
                  className="h-[88px] rounded-xl bg-white/[0.025] border border-border animate-pulse"
                />
              ))}
            </div>
          ) : results && displayProducts.length > 0 ? (
            <>
              {/* Count + sort */}
              <div className="flex items-center justify-between mb-3">
                <p className="font-mono text-[11px] text-muted-foreground/60 tabular-nums">
                  {t('search.result', { count: results.total })}
                </p>
                <select
                  value={sort}
                  onChange={(e) => setFilter('sort', e.target.value)}
                  className="bg-white/[0.04] border border-border rounded-lg px-2 py-1.5 text-[12px] focus:outline-none focus:border-primary/30 transition-colors"
                >
                  <option value="recent">{t('search.sortRecent')}</option>
                  <option value="price_asc">{t('search.sortPriceAsc')}</option>
                  <option value="price_desc">{t('search.sortPriceDesc')}</option>
                  <option value="alpha">{t('search.sortAlpha')}</option>
                </select>
              </div>
              <ul className="grid grid-cols-2 gap-2">
                {displayProducts.map((product) => {
                  const isWatched = watchedSkus.has(product.sku)
                  const isBusy = watchingInProgress === product.sku
                  const watchButton = (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={(e) => {
                        e.stopPropagation()
                        if (isWatched) handleUnwatch(product.sku)
                        else handleWatch(product.sku)
                      }}
                      className={`w-24 border rounded-lg py-1.5 text-[12px] text-center transition-colors ${
                        isWatched
                          ? 'border-primary/40 bg-primary/10 text-primary'
                          : 'border-border text-muted-foreground hover:text-foreground'
                      } ${isBusy ? 'opacity-50' : ''}`}
                    >
                      {isBusy ? '...' : isWatched ? t('search.watching') : t('search.watch')}
                    </button>
                  )
                  const isSelected = selectedSku === product.sku
                  return (
                    <li key={product.sku}>
                      <div
                        role="button"
                        tabIndex={0}
                        onClick={() => setSelectedSku(isSelected ? null : product.sku)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ')
                            setSelectedSku(isSelected ? null : product.sku)
                        }}
                        className={`cursor-pointer rounded-xl transition-colors ${isSelected ? 'ring-1 ring-primary/60' : ''}`}
                      >
                        <WineCard
                          product={product}
                          storeNames={storeNames}
                          watchSlot={watchButton}
                        />
                      </div>
                    </li>
                  )
                })}
              </ul>

              {/* Pagination */}
              {pages > 1 && (
                <div className="flex items-center gap-1.5 mt-6 font-mono text-[12px]">
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
                    if (pages <= 7) p = i + 1
                    else if (page <= 4) p = i + 1
                    else if (page >= pages - 3) p = pages - 6 + i
                    else p = page - 3 + i
                    return (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setPage(p)}
                        className={`w-7 h-7 rounded-lg text-[11px] transition-colors ${
                          p === page
                            ? 'bg-primary/10 text-primary border border-primary/30'
                            : 'text-muted-foreground hover:text-foreground hover:bg-white/[0.04]'
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
            !loading && (
              <EmptyState
                icon={<Wine size={28} />}
                title={t('search.noResults')}
                description={t('search.noResultsDesc')}
                cta={
                  hasSecondaryFilters || category
                    ? { label: t('search.reset'), onClick: resetFilters }
                    : undefined
                }
                secondaryCta={
                  !query
                    ? {
                        label: t('search.askSommelier'),
                        onClick: () => navigate('/chat'),
                      }
                    : undefined
                }
              />
            )
          )}
        </div>
      </div>
    </div>
  )
}

export default SearchPage
