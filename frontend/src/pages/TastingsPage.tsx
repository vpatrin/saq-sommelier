import { useState, useCallback, useEffect, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { CaretDown, MagnifyingGlass, NotePencil, PencilSimple, Plus } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import type { TFunction } from 'i18next'
import { useApiClient, ApiError } from '@/lib/api'
import type { TastingNoteOut } from '@/lib/types'
import { getBucket, ratingColor } from '@/lib/rating'
import { CATEGORY_DOT } from '@/lib/utils'
import EmptyState from '@/components/EmptyState'
import TastingForm from '@/components/TastingForm'
import NoteViewModal from '@/components/NoteViewModal'

const PAGE_SIZE = 20

// TODO: pass i18n.language when runtime locale switching is implemented
const groupLabelFmt = new Intl.DateTimeFormat('fr-CA', {
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})
const noteDateFmt = new Intl.DateTimeFormat('fr-CA', { day: 'numeric', month: 'short' })

// Groups an ordered list of tasting notes by their tasted_at date label.
// Returns pairs of [label, notes[]] in the order they first appear.
function groupByDate(notes: TastingNoteOut[], t: TFunction): [string, TastingNoteOut[]][] {
  const today = new Date().toISOString().slice(0, 10)
  const yesterday = new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)

  const map = new Map<string, TastingNoteOut[]>()
  for (const note of notes) {
    let label: string
    if (note.tasted_at === today) label = t('time.today')
    else if (note.tasted_at === yesterday) label = t('time.yesterday')
    else label = groupLabelFmt.format(new Date(note.tasted_at + 'T00:00:00'))
    const group = map.get(label) ?? []
    group.push(note)
    map.set(label, group)
  }
  return [...map.entries()]
}

function TastingsPage() {
  const apiClient = useApiClient()
  const { t } = useTranslation()

  const [notes, setNotes] = useState<TastingNoteOut[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [filter, setFilter] = useState('')
  const [sort, setSort] = useState<'date-desc' | 'date-asc' | 'rating-desc' | 'rating-asc'>(
    'date-desc',
  )
  const [fetchKey, setFetchKey] = useState(0)
  const [addNoteOpen, setAddNoteOpen] = useState(false)
  const [viewNote, setViewNote] = useState<{ note: TastingNoteOut; mode: 'view' | 'edit' } | null>(
    null,
  )

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

  const handleDelete = useCallback(
    async (id: number) => {
      setViewNote(null)
      // Capture removed item + index inside the updater so this callback doesn't depend on `notes`
      let removed: TastingNoteOut | undefined
      let removedIdx = -1
      setNotes((prev) => {
        removedIdx = prev.findIndex((n) => n.id === id)
        removed = prev[removedIdx]
        return prev.filter((n) => n.id !== id)
      })

      try {
        await apiClient(`/tastings/${id}`, { method: 'DELETE' })
      } catch (err) {
        // Restore at original position so the list doesn't visibly reorder on rollback
        if (removed) {
          setNotes((prev) => {
            const next = [...prev]
            next.splice(removedIdx, 0, removed!)
            return next
          })
        }
        console.error('Delete failed', err instanceof ApiError ? err.detail : err)
      }
    },
    [apiClient],
  )

  const handleNoteSaved = useCallback((note: TastingNoteOut) => {
    setNotes((prev) => [note, ...prev])
    setAddNoteOpen(false)
  }, [])

  const handleNoteUpdated = useCallback((updated: TastingNoteOut) => {
    setNotes((prev) => prev.map((n) => (n.id === updated.id ? updated : n)))
    setViewNote({ note: updated, mode: 'view' })
  }, [])

  // useCallback so WineSearch's Escape handler (which has onCancel in its dep array) doesn't re-register on every render
  const openModal = useCallback(() => setAddNoteOpen(true), [])
  const closeModal = useCallback(() => setAddNoteOpen(false), [])

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    const base = q
      ? notes.filter((n) => (n.product_name ?? n.sku).toLowerCase().includes(q))
      : notes
    if (sort === 'date-asc')
      return [...base].sort((a, b) =>
        a.tasted_at !== b.tasted_at
          ? a.tasted_at.localeCompare(b.tasted_at)
          : a.created_at.localeCompare(b.created_at),
      )
    if (sort === 'rating-desc') return [...base].sort((a, b) => b.rating - a.rating)
    if (sort === 'rating-asc') return [...base].sort((a, b) => a.rating - b.rating)
    // date-desc: sort by tasted_at desc, then created_at desc for same-day notes
    return [...base].sort((a, b) =>
      a.tasted_at !== b.tasted_at
        ? b.tasted_at.localeCompare(a.tasted_at)
        : b.created_at.localeCompare(a.created_at),
    )
  }, [notes, filter, sort])

  // Only group by date when sorting by date — rating sort gets a flat list
  const grouped = useMemo(
    () =>
      sort === 'rating-desc' || sort === 'rating-asc'
        ? [['', filtered] as [string, TastingNoteOut[]]]
        : groupByDate(filtered, t),
    [filtered, sort, t],
  )

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
            {t('journal.failedToLoad')} —{' '}
            <button
              type="button"
              className="underline hover:text-foreground transition-colors"
              onClick={() => setFetchKey((k) => k + 1)}
            >
              {t('journal.retry')}
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
        <div className="flex items-center gap-2.5 mb-1">
          <h1 className="text-2xl font-light">{t('journal.title')}</h1>
          {notes.length > 0 && (
            <span className="font-mono text-[11px] text-muted-foreground/60 tabular-nums">
              {notes.length}
            </span>
          )}
        </div>
        <p className="text-[13px] font-light text-muted-foreground/50 mb-5">
          {t('journal.subtitle')}
        </p>

        {notes.length === 0 ? (
          /* Empty state — centered CTA, no dashed row */
          <EmptyState
            icon={<NotePencil size={28} />}
            title={t('journal.emptyTitle')}
            description={t('journal.emptyDesc')}
            cta={{ label: t('journal.addFirstNote'), onClick: openModal }}
          />
        ) : (
          <>
            {/* Add-note CTA — dashed row, only shown when there are notes */}
            <button
              type="button"
              onClick={openModal}
              className="w-full flex items-center gap-3 px-4 py-3.5 mb-6 rounded-xl border border-dashed border-border hover:border-primary/30 hover:bg-primary/[0.03] transition-colors group"
            >
              <div className="w-8 h-8 rounded-lg bg-primary/[0.08] border border-primary/10 flex items-center justify-center shrink-0 text-primary/60 group-hover:text-primary/80 transition-colors">
                <Plus size={15} weight="bold" />
              </div>
              <p className="text-[13px] font-medium text-muted-foreground/70 group-hover:text-foreground transition-colors">
                {t('journal.addNote')}
              </p>
            </button>

            {/* Filter + sort */}
            <div className="flex items-center gap-3 mb-6">
              <div className="relative flex-1">
                <MagnifyingGlass
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
                />
                <input
                  type="text"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder={t('journal.searchPlaceholder')}
                  className="w-full h-9 pl-8 pr-3 rounded-lg bg-white/[0.04] border border-border text-[13px] placeholder:text-muted-foreground/40 focus:outline-none focus:border-primary/30 transition-colors"
                />
              </div>
              <div className="relative shrink-0">
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as typeof sort)}
                  className="h-9 pl-3 pr-8 rounded-lg bg-white/[0.04] border border-border text-[13px] text-muted-foreground focus:outline-none focus:border-primary/30 transition-colors appearance-none cursor-pointer"
                >
                  <option value="date-desc">{t('journal.sortNewest')}</option>
                  <option value="date-asc">{t('journal.sortOldest')}</option>
                  <option value="rating-desc">{t('journal.sortRatingDesc')}</option>
                  <option value="rating-asc">{t('journal.sortRatingAsc')}</option>
                </select>
                <CaretDown
                  size={11}
                  weight="bold"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground/50 pointer-events-none"
                />
              </div>
            </div>

            {filtered.length === 0 ? (
              <EmptyState icon={<MagnifyingGlass size={28} />} title={t('journal.emptySearch')} />
            ) : (
              <>
                {grouped.map(([label, group]) => (
                  <div key={label} className="mb-6">
                    {label && (
                      <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/40 mb-2">
                        {label}
                      </p>
                    )}
                    <ul className="flex flex-col gap-3">
                      {group.map((note) => {
                        const name = note.product_name ?? note.sku
                        const bucket = getBucket(note.rating)
                        const isKnownCategory = note.product_category
                          ? !!CATEGORY_DOT[note.product_category]
                          : false
                        return (
                          <li
                            key={note.id}
                            role="button"
                            tabIndex={0}
                            aria-label={name}
                            onClick={() => setViewNote({ note, mode: 'view' })}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ')
                                setViewNote({ note, mode: 'view' })
                            }}
                            className="group relative rounded-xl border border-border bg-white/[0.025] px-[18px] pt-3 pb-3 transition-colors hover:border-primary/20 cursor-pointer"
                          >
                            {/* Top: name + score + edit */}
                            <div className="flex items-start justify-between gap-3 mb-1.5">
                              <p className="text-[15px] font-semibold leading-snug line-clamp-2 flex-1 min-w-0">
                                {name}
                              </p>
                              <div className="flex items-center gap-2 shrink-0">
                                <span
                                  className={`font-mono text-[22px] font-bold leading-none ${bucket.color}`}
                                >
                                  {note.rating}
                                </span>
                                <div className="w-16 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                                  <div
                                    className="h-full rounded-full"
                                    style={{
                                      width: `${note.rating}%`,
                                      background: ratingColor(note.rating),
                                    }}
                                  />
                                </div>
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    setViewNote({ note, mode: 'edit' })
                                  }}
                                  className="opacity-0 group-hover:opacity-100 w-6 h-6 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-foreground hover:bg-white/[0.06] transition-all"
                                  aria-label={t('journal.editNote')}
                                >
                                  <PencilSimple size={13} weight="bold" />
                                </button>
                              </div>
                            </div>

                            {/* Category pill + region · grapes — same line */}
                            {(note.product_category || note.product_region) && (
                              <div className="flex items-center gap-2 mb-2">
                                {note.product_category && (
                                  <span
                                    className="text-[11px] px-1.5 py-0.5 rounded border"
                                    style={
                                      isKnownCategory
                                        ? {
                                            color: 'var(--color-primary)',
                                            borderColor: 'rgba(200,146,72,0.25)',
                                            background: 'rgba(200,146,72,0.06)',
                                          }
                                        : {
                                            color: 'rgba(255,255,255,0.5)',
                                            borderColor: 'rgba(255,255,255,0.08)',
                                            background: 'rgba(255,255,255,0.04)',
                                          }
                                    }
                                  >
                                    {note.product_category}
                                  </span>
                                )}
                                {note.product_region && (
                                  <span className="font-mono text-[11px] text-white/60 truncate">
                                    {note.product_region}
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Grape(s) — own line below category + region */}
                            {note.product_grape && (
                              <p className="font-mono text-[11px] text-white/40 mb-2 truncate">
                                {note.product_grape}
                              </p>
                            )}

                            {/* Impressions — 2 lines max, or pairing if no impressions */}
                            {(note.notes || note.pairing) && (
                              <p className="text-[13px] text-white/70 leading-relaxed line-clamp-2 mb-2">
                                {note.notes ?? note.pairing}
                              </p>
                            )}

                            {/* Bottom: date + price */}
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-[11px] text-white/40">
                                {noteDateFmt.format(new Date(note.tasted_at + 'T00:00:00'))}
                              </span>
                              {note.product_price && (
                                <span className="font-mono text-[13px] font-light text-primary/70">
                                  {note.product_price} $
                                </span>
                              )}
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
                    {loadingMore ? t('journal.loading') : t('journal.loadMore')}
                  </button>
                )}
              </>
            )}
          </>
        )}
      </div>

      {/* Add-note modal — portaled to body to escape overflow:hidden on <main> */}
      {addNoteOpen &&
        createPortal(
          <div className="fixed inset-0 z-50 flex items-center justify-center">
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={closeModal} />
            <div className="relative w-full max-w-lg mx-4 rounded-xl bg-[#0e0e12] border border-border shadow-2xl p-6">
              <p className="text-[14px] font-medium mb-4">{t('tastingForm.addTitle')}</p>
              <TastingForm onSave={handleNoteSaved} onCancel={closeModal} />
            </div>
          </div>,
          document.body,
        )}

      {viewNote !== null && (
        <NoteViewModal
          note={viewNote.note}
          initialMode={viewNote.mode}
          onClose={() => setViewNote(null)}
          onDelete={handleDelete}
          onUpdated={handleNoteUpdated}
        />
      )}
    </div>
  )
}

export default TastingsPage
