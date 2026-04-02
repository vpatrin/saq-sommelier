import { useState, useCallback, useEffect, useMemo } from 'react'
import { MagnifyingGlass, NotePencil, X } from '@phosphor-icons/react'
import { useApiClient, ApiError } from '@/lib/api'
import type { TastingNoteOut } from '@/lib/types'
import EmptyState from '@/components/EmptyState'

const PAGE_SIZE = 20

const groupLabelFmt = new Intl.DateTimeFormat('fr-CA', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})
const noteDateFmt = new Intl.DateTimeFormat('fr-CA', { day: 'numeric', month: 'short' })

// Groups an ordered list of tasting notes by their tasted_at date label.
// Returns pairs of [label, notes[]] in the order they first appear.
function groupByDate(notes: TastingNoteOut[]): [string, TastingNoteOut[]][] {
  const today = new Date().toISOString().slice(0, 10)
  const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)

  const map = new Map<string, TastingNoteOut[]>()
  for (const note of notes) {
    let label: string
    if (note.tasted_at === today) label = "Aujourd'hui"
    else if (note.tasted_at === yesterday) label = 'Hier'
    else label = groupLabelFmt.format(new Date(note.tasted_at + 'T00:00:00'))
    const group = map.get(label) ?? []
    group.push(note)
    map.set(label, group)
  }
  return [...map.entries()]
}

function TastingsPage() {
  const apiClient = useApiClient()

  const [notes, setNotes] = useState<TastingNoteOut[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [filter, setFilter] = useState('')
  const [fetchKey, setFetchKey] = useState(0)
  const [deleteState, setDeleteState] = useState<{
    id: number
    status: 'confirm' | 'error'
  } | null>(null)

  const fetchPage = useCallback(
    async (offset: number) => {
      const data = await apiClient<TastingNoteOut[]>(
        `/tastings?limit=${PAGE_SIZE}&offset=${offset}`,
      )
      return data
    },
    [apiClient],
  )

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchPage(0)
      .then((data) => {
        if (!cancelled) {
          setNotes(data)
          setHasMore(data.length === PAGE_SIZE)
          setLoadError(false)
        }
      })
      .catch(() => {
        if (!cancelled) setLoadError(true)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [fetchPage, fetchKey])

  const handleLoadMore = useCallback(async () => {
    setLoadingMore(true)
    try {
      const data = await fetchPage(notes.length)
      setNotes((prev) => [...prev, ...data])
      setHasMore(data.length === PAGE_SIZE)
    } catch {
      // load-more failure is non-critical — user can retry by clicking again
    } finally {
      setLoadingMore(false)
    }
  }, [fetchPage, notes.length])

  const handleDeleteClick = useCallback((id: number) => {
    setDeleteState({ id, status: 'confirm' })
  }, [])

  const handleDeleteCancel = useCallback(() => {
    setDeleteState(null)
  }, [])

  const handleDeleteConfirm = useCallback(
    async (id: number) => {
      // Optimistic remove
      const removed = notes.find((n) => n.id === id)
      setNotes((prev) => prev.filter((n) => n.id !== id))
      setDeleteState(null)

      try {
        await apiClient(`/tastings/${id}`, { method: 'DELETE' })
      } catch (err) {
        // Roll back
        if (removed) setNotes((prev) => [removed, ...prev.filter((n) => n.id !== id)])
        setDeleteState({ id, status: 'error' })
        console.error('Delete failed', err instanceof ApiError ? err.detail : err)
      }
    },
    [apiClient, notes],
  )

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return notes
    return notes.filter((n) => (n.product_name ?? n.sku).toLowerCase().includes(q))
  }, [notes, filter])

  const grouped = useMemo(() => groupByDate(filtered), [filtered])

  if (loading) {
    return (
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-2xl mx-auto flex flex-col gap-3">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="h-[72px] rounded-xl bg-white/[0.025] border border-border animate-pulse"
            />
          ))}
        </div>
      </div>
    )
  }

  if (loadError) {
    return (
      <div className="flex-1 overflow-y-auto p-8">
        <div className="max-w-2xl mx-auto">
          <p className="text-[13px] text-muted-foreground/60">
            Impossible de charger le journal —{' '}
            <button
              type="button"
              className="underline hover:text-foreground transition-colors"
              onClick={() => setFetchKey((k) => k + 1)}
            >
              réessayer
            </button>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto p-8">
      <div className="max-w-2xl mx-auto">
        {/* Header */}
        <div className="flex items-baseline gap-2.5 mb-1">
          <h1 className="text-2xl font-light">Journal</h1>
          {notes.length > 0 && (
            <span className="font-mono text-[11px] text-muted-foreground/60 tabular-nums">
              {notes.length}
            </span>
          )}
        </div>
        <p className="text-[13px] font-light text-muted-foreground/50 mb-6">
          Vos impressions construisent votre profil gustatif.
        </p>

        {notes.length === 0 ? (
          <EmptyState
            icon={<NotePencil size={28} />}
            title="Aucune note pour l'instant"
            description="Ajoutez votre première note après avoir dégusté un vin."
            cta={{ label: 'Ajouter une note', onClick: () => {} }}
          />
        ) : (
          <>
            {/* Filter */}
            <div className="relative mb-6">
              <MagnifyingGlass
                size={14}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
              />
              <input
                type="text"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder="Filtrer par vin…"
                className="w-full h-9 pl-8 pr-3 rounded-lg bg-white/[0.04] border border-border text-[13px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors"
              />
            </div>

            {filtered.length === 0 ? (
              <EmptyState icon={<MagnifyingGlass size={28} />} title="Aucun résultat" />
            ) : (
              <>
                {grouped.map(([label, group]) => (
                  <div key={label} className="mb-6">
                    <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/40 mb-2">
                      {label}
                    </p>
                    <ul className="flex flex-col gap-2">
                      {group.map((note) => {
                        const ds = deleteState?.id === note.id ? deleteState.status : undefined
                        const name = note.product_name ?? note.sku

                        return (
                          <li
                            key={note.id}
                            className="group relative rounded-xl border border-border bg-white/[0.025] px-[18px] py-4 transition-colors hover:border-primary/20"
                          >
                            <div className="flex items-start justify-between gap-3">
                              {/* Left: wine info */}
                              <div className="flex-1 min-w-0">
                                <p className="text-[14px] font-medium leading-snug truncate">
                                  {name}
                                </p>
                                {note.notes && (
                                  <p className="text-[12px] font-light text-muted-foreground/70 mt-1 truncate">
                                    {note.notes}
                                  </p>
                                )}
                                {note.pairing && (
                                  <p className="text-[12px] font-light text-muted-foreground/50 mt-0.5 truncate">
                                    <span className="text-muted-foreground/40">Accord : </span>
                                    {note.pairing}
                                  </p>
                                )}
                              </div>

                              {/* Right: rating + date + actions */}
                              <div className="flex flex-col items-end gap-1.5 flex-shrink-0">
                                <span className="font-mono text-[13px] font-medium text-primary/90">
                                  {note.rating} / 100
                                </span>
                                <span className="font-mono text-[10px] text-muted-foreground/40">
                                  {noteDateFmt.format(new Date(note.tasted_at + 'T00:00:00'))}
                                </span>

                                {/* Delete actions */}
                                {ds === 'confirm' ? (
                                  <div className="flex items-center gap-2 text-[11px]">
                                    <span className="text-muted-foreground/50">Supprimer ?</span>
                                    <button
                                      type="button"
                                      onClick={() => handleDeleteConfirm(note.id)}
                                      className="text-destructive hover:text-destructive/80 transition-colors"
                                    >
                                      Oui
                                    </button>
                                    <button
                                      type="button"
                                      onClick={handleDeleteCancel}
                                      className="text-muted-foreground hover:text-foreground transition-colors"
                                    >
                                      Non
                                    </button>
                                  </div>
                                ) : ds === 'error' ? (
                                  <p className="text-[11px] text-destructive">
                                    Impossible de supprimer —{' '}
                                    <button
                                      type="button"
                                      className="underline"
                                      onClick={() => handleDeleteConfirm(note.id)}
                                    >
                                      réessayer
                                    </button>
                                  </p>
                                ) : (
                                  <button
                                    type="button"
                                    onClick={() => handleDeleteClick(note.id)}
                                    className="opacity-0 group-hover:opacity-100 w-6 h-6 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-all"
                                    aria-label="Supprimer la note"
                                  >
                                    <X size={13} weight="bold" />
                                  </button>
                                )}
                              </div>
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                ))}

                {hasMore && (
                  <button
                    type="button"
                    onClick={handleLoadMore}
                    disabled={loadingMore}
                    className="w-full mt-2 py-2.5 rounded-lg border border-border text-[13px] text-muted-foreground/60 hover:text-foreground hover:border-border/80 hover:bg-white/[0.02] transition-colors disabled:opacity-40"
                  >
                    {loadingMore ? 'Chargement…' : 'Afficher plus'}
                  </button>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default TastingsPage
