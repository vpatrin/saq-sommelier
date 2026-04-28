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

  if (loadError) {
    return (
      <div className="flex-1 overflow-y-auto p-8">
        <div className="mx-auto max-w-2xl">
          <p className="text-muted-foreground/60 text-[13px]">
            {t('journal.failedToLoad')} —{' '}
            <button
              type="button"
              className="hover:text-foreground underline transition-colors"
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
      <div className="mx-auto max-w-2xl">
        {/* Header */}
        <div className="mb-1 flex items-center gap-2.5">
          <h1 className="text-2xl font-light">{t('journal.title')}</h1>
          {notes.length > 0 && (
            <span className="text-muted-foreground/60 font-mono text-[11px] tabular-nums">
              {notes.length}
            </span>
          )}
        </div>
        <p className="text-muted-foreground/50 mb-5 text-[13px] font-light">
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
              className="border-border hover:border-primary/30 hover:bg-primary/[0.03] group mb-6 flex w-full items-center gap-3 rounded-xl border border-dashed px-4 py-3.5 transition-colors"
            >
              <div className="bg-primary/[0.08] border-primary/10 text-primary/60 group-hover:text-primary/80 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-colors">
                <Plus size={15} weight="bold" />
              </div>
              <p className="text-muted-foreground/70 group-hover:text-foreground text-[13px] font-medium transition-colors">
                {t('journal.addNote')}
              </p>
            </button>

            {/* Filter + sort */}
            <div className="mb-6 flex items-center gap-3">
              <div className="relative flex-1">
                <MagnifyingGlass
                  size={14}
                  className="text-muted-foreground/50 pointer-events-none absolute top-1/2 left-3 -translate-y-1/2"
                />
                <input
                  type="text"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder={t('journal.searchPlaceholder')}
                  className="border-border placeholder:text-muted-foreground/40 focus:border-primary/30 h-9 w-full rounded-lg border bg-white/[0.04] pr-3 pl-8 text-[13px] transition-colors focus:outline-none"
                />
              </div>
              <div className="relative shrink-0">
                <select
                  value={sort}
                  onChange={(e) => setSort(e.target.value as typeof sort)}
                  className="border-border text-muted-foreground focus:border-primary/30 h-9 cursor-pointer appearance-none rounded-lg border bg-white/[0.04] pr-8 pl-3 text-[13px] transition-colors focus:outline-none"
                >
                  <option value="date-desc">{t('journal.sortNewest')}</option>
                  <option value="date-asc">{t('journal.sortOldest')}</option>
                  <option value="rating-desc">{t('journal.sortRatingDesc')}</option>
                  <option value="rating-asc">{t('journal.sortRatingAsc')}</option>
                </select>
                <CaretDown
                  size={11}
                  weight="bold"
                  className="text-muted-foreground/50 pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2"
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
                      <p className="text-muted-foreground/40 mb-2 font-mono text-[10px] tracking-widest uppercase">
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
                            className="group border-border hover:border-primary/20 relative cursor-pointer rounded-xl border bg-white/[0.025] px-[18px] pt-3 pb-3 transition-colors"
                          >
                            {/* Top: name + score + edit */}
                            <div className="mb-1.5 flex items-start justify-between gap-3">
                              <p className="line-clamp-2 min-w-0 flex-1 text-[15px] leading-snug font-semibold">
                                {name}
                              </p>
                              <div className="flex shrink-0 items-center gap-2">
                                <span
                                  className={`font-mono text-[22px] leading-none font-bold ${bucket.color}`}
                                >
                                  {note.rating}
                                </span>
                                <div className="h-1.5 w-16 overflow-hidden rounded-full bg-white/[0.06]">
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
                                  className="text-muted-foreground/40 hover:text-foreground flex h-6 w-6 items-center justify-center rounded-md opacity-0 transition-all group-hover:opacity-100 hover:bg-white/[0.06]"
                                  aria-label={t('journal.editNote')}
                                >
                                  <PencilSimple size={13} weight="bold" />
                                </button>
                              </div>
                            </div>

                            {/* Category pill + region · grapes — same line */}
                            {(note.product_category || note.product_region) && (
                              <div className="mb-2 flex items-center gap-2">
                                {note.product_category && (
                                  <span
                                    className="rounded border px-1.5 py-0.5 text-[11px]"
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
                                  <span className="truncate font-mono text-[11px] text-white/60">
                                    {note.product_region}
                                  </span>
                                )}
                              </div>
                            )}

                            {/* Grape(s) — own line below category + region */}
                            {note.product_grape && (
                              <p className="mb-2 truncate font-mono text-[11px] text-white/40">
                                {note.product_grape}
                              </p>
                            )}

                            {/* Impressions — 2 lines max, or pairing if no impressions */}
                            {(note.notes || note.pairing) && (
                              <p className="mb-2 line-clamp-2 text-[13px] leading-relaxed text-white/70">
                                {note.notes ?? note.pairing}
                              </p>
                            )}

                            {/* Bottom: date + price */}
                            <div className="flex items-center justify-between">
                              <span className="font-mono text-[11px] text-white/40">
                                {noteDateFmt.format(new Date(note.tasted_at + 'T00:00:00'))}
                              </span>
                              {note.product_price && (
                                <span className="text-primary/70 font-mono text-[13px] font-light">
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
                    className="border-border text-muted-foreground/60 hover:text-foreground hover:border-border/80 mt-2 w-full rounded-lg border py-2.5 text-[13px] transition-colors hover:bg-white/[0.02] disabled:opacity-40"
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
            <div className="border-border relative mx-4 w-full max-w-lg rounded-xl border bg-[#0e0e12] p-6 shadow-2xl">
              <p className="mb-4 text-[14px] font-medium">{t('tastingForm.addTitle')}</p>
              <TastingForm onSave={handleNoteSaved} onCancel={closeModal} />
            </div>
          </div>,
          document.body,
        )}

      {viewNote !== null && (
        <NoteViewModal
          key={viewNote.note.id}
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
