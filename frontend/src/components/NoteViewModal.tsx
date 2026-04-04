import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { ArrowLeft, PencilSimple, Trash } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useApiClient } from '@/lib/api'
import { useAuth } from '@/contexts/AuthContext'
import { formatOrigin, CATEGORY_DOT } from '@/lib/utils'
import { getBucket, ratingColor } from '@/lib/rating'
import TastingForm from '@/components/TastingForm'
import type { TastingNoteOut, ProductOut } from '@/lib/types'

const dateFmt = new Intl.DateTimeFormat('fr-CA', { day: 'numeric', month: 'long', year: 'numeric' })

function saqUrl(sku: string) {
  return `https://www.saq.com/fr/${sku}`
}

interface NoteViewModalProps {
  note: TastingNoteOut
  onClose: () => void
  onDelete: (id: number) => void
  onUpdated: (note: TastingNoteOut) => void
  initialMode?: 'view' | 'edit'
}

function NoteViewModal({
  note,
  onClose,
  onDelete,
  onUpdated,
  initialMode = 'view',
}: NoteViewModalProps) {
  const apiClient = useApiClient()
  const { user } = useAuth()
  const { t } = useTranslation()
  const userId = user ? `user:${user.id}` : null

  const [mode, setMode] = useState<'view' | 'edit'>(initialMode)
  const [currentNote, setCurrentNote] = useState(note)

  // Product data — fetched once on open
  const [product, setProduct] = useState<ProductOut | null>(null)

  // Watch state
  const [watched, setWatched] = useState(false)
  const [watchLoading, setWatchLoading] = useState(false)

  // Delete confirm
  const [confirmDelete, setConfirmDelete] = useState(false)

  // Sync mode and note if a different note is passed without unmounting the modal
  useEffect(() => {
    setMode(initialMode)
    setCurrentNote(note)
    setProduct(null)
    setConfirmDelete(false)
  }, [note.id]) // eslint-disable-line react-hooks/exhaustive-deps -- intentionally only reset when a different note is opened, not on every prop change

  useEffect(() => {
    let cancelled = false

    apiClient<ProductOut>(`/products/${currentNote.sku}`)
      .then((p) => {
        if (!cancelled) setProduct(p)
      })
      .catch(() => {
        /* non-critical — degrade gracefully */
      })

    // Derive watch status from the full list — no single-item check endpoint exists yet.
    // TODO: add GET /watches/:sku before watch lists grow large.
    if (userId) {
      apiClient<{ sku: string }[]>(`/watches?user_id=${encodeURIComponent(userId)}`)
        .then((list) => {
          if (!cancelled) setWatched(list.some((w) => w.sku === currentNote.sku))
        })
        .catch(() => {
          /* non-critical */
        })
    }

    return () => {
      cancelled = true
    }
  }, [apiClient, currentNote.sku, userId])

  const handleWatch = useCallback(async () => {
    setWatchLoading(true)
    const wasWatched = watched
    setWatched(!wasWatched)
    try {
      if (wasWatched) {
        await apiClient(`/watches/${currentNote.sku}?user_id=${encodeURIComponent(userId ?? '')}`, {
          method: 'DELETE',
        })
      } else {
        await apiClient('/watches', {
          method: 'POST',
          body: JSON.stringify({ sku: currentNote.sku }),
        })
      }
    } catch {
      setWatched(wasWatched) // rollback
    } finally {
      setWatchLoading(false)
    }
  }, [apiClient, currentNote.sku, userId, watched])

  const handleNoteSaved = useCallback(
    (updated: TastingNoteOut) => {
      setCurrentNote(updated)
      onUpdated(updated)
      setMode('view')
    },
    [onUpdated],
  )

  const handleDeleteConfirm = useCallback(() => {
    setConfirmDelete(false)
    onClose()
    onDelete(currentNote.id)
  }, [onClose, onDelete, currentNote.id])

  const bucket = getBucket(currentNote.rating)
  const origin = product ? formatOrigin(product) : null
  const dotColor = product?.category ? (CATEGORY_DOT[product.category] ?? null) : null

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg mx-4 rounded-xl bg-[#0e0e12] border border-border shadow-2xl flex flex-col max-h-[90vh]">
        {/* Top bar */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-1.5 text-[12px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
          >
            <ArrowLeft size={13} weight="bold" />
            {t('nav.journal')}
          </button>
          {mode === 'view' && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setMode('edit')}
                className="w-7 h-7 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-foreground hover:bg-white/[0.04] transition-all"
                aria-label={t('noteView.edit')}
              >
                <PencilSimple size={14} />
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="w-7 h-7 flex items-center justify-center rounded-md text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 transition-all"
                aria-label={t('noteView.delete')}
              >
                <Trash size={14} />
              </button>
            </div>
          )}
          {mode === 'edit' && <p className="text-[13px] font-medium">{t('journal.editNote')}</p>}
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto p-5 flex flex-col gap-4">
          {mode === 'view' ? (
            <>
              {/* Wine header — styled like WineCard but with rating instead of price */}
              <div
                className="rounded-xl border border-border bg-white/[0.025] px-[18px] py-3 flex flex-col justify-between gap-3"
                style={{ borderLeft: '3px solid rgba(200,146,72,0.35)' }}
              >
                {/* Top: dot + name + rating */}
                <div className="flex items-start gap-2.5">
                  {dotColor && (
                    <span className={`mt-[5px] w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
                  )}
                  <div className="flex items-start justify-between gap-3 flex-1 min-w-0">
                    <a
                      href={saqUrl(currentNote.sku)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[14px] font-medium leading-snug hover:text-primary transition-colors line-clamp-2"
                    >
                      {currentNote.product_name ?? currentNote.sku}
                    </a>
                    <p className="font-mono text-[18px] font-light text-primary/90 leading-none whitespace-nowrap flex-shrink-0">
                      {currentNote.rating}{' '}
                      <span className="text-[12px] text-muted-foreground/40">/ 100</span>
                    </p>
                  </div>
                </div>

                {/* Middle: region pill + grapes */}
                {(origin || product?.grape) && (
                  <div className="ml-[18px] flex flex-col gap-1 min-w-0">
                    {origin && (
                      <span className="text-[10px] px-2 py-0.5 rounded border bg-white/[0.04] text-muted-foreground border-white/[0.06] truncate inline-block self-start max-w-full">
                        {origin}
                      </span>
                    )}
                    {product?.grape && (
                      <p className="font-mono text-[10px] text-muted-foreground/50 truncate">
                        {product.grape}
                      </p>
                    )}
                  </div>
                )}

                {/* Bottom: availability + watch */}
                <div className="flex items-center justify-between gap-3 ml-[18px]">
                  <div className="flex items-center gap-2 min-w-0">
                    {product?.online_availability && (
                      <span className="text-[10px] text-green-500">{t('availability.online')}</span>
                    )}
                    {product?.online_availability &&
                      (product?.store_availability?.length ?? 0) > 0 && (
                        <span className="text-[10px] text-muted-foreground/50">·</span>
                      )}
                    {(product?.store_availability?.length ?? 0) > 0 && (
                      <span className="text-[10px] text-green-500">
                        {t('availability.inStores_other', {
                          count: product!.store_availability!.length,
                        })}
                      </span>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={handleWatch}
                    disabled={watchLoading || !userId}
                    className={`text-[11px] px-3 py-1 rounded-lg border transition-colors disabled:opacity-40 ${
                      watched
                        ? 'border-primary/30 bg-primary/[0.08] text-primary/80 hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30'
                        : 'border-border text-muted-foreground/60 hover:border-primary/30 hover:text-primary/80 hover:bg-primary/[0.04]'
                    }`}
                  >
                    {watched ? `${t('noteView.watching')} ✓` : t('noteView.watch')}
                  </button>
                </div>
              </div>

              {/* Score bar */}
              <div>
                <div className="flex items-center gap-3 mb-1.5">
                  <div className="flex-1 h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${currentNote.rating}%`,
                        background: ratingColor(currentNote.rating),
                      }}
                    />
                  </div>
                </div>
                <p className="text-[11px] text-muted-foreground/50 italic">{bucket.description}</p>
              </div>

              {/* Impressions */}
              {currentNote.notes && (
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/40 mb-2">
                    {t('tastingForm.notes')}
                  </p>
                  <p className="text-[14px] font-light text-muted-foreground/80 leading-relaxed">
                    {currentNote.notes}
                  </p>
                </div>
              )}

              {/* Pairing */}
              {currentNote.pairing && (
                <div>
                  <p className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground/40 mb-2">
                    {t('tastingForm.pairing')}
                  </p>
                  <p className="text-[14px] font-light text-muted-foreground/80 leading-relaxed">
                    {currentNote.pairing}
                  </p>
                </div>
              )}

              {/* Date */}
              <p className="font-mono text-[11px] text-muted-foreground/30 pt-2 border-t border-border">
                {dateFmt.format(new Date(currentNote.tasted_at + 'T00:00:00'))}
              </p>
            </>
          ) : (
            // Edit mode — TastingForm pre-filled, wine locked (no search, no X)
            <TastingForm
              noteId={currentNote.id}
              initialProduct={
                product ?? ({ sku: currentNote.sku, name: currentNote.product_name } as ProductOut)
              }
              initialRating={currentNote.rating}
              initialNotes={currentNote.notes ?? undefined}
              initialPairing={currentNote.pairing ?? undefined}
              initialTastedAt={currentNote.tasted_at}
              onSave={handleNoteSaved}
              onCancel={() => setMode('view')}
            />
          )}
        </div>
      </div>

      {/* Delete confirm — stacked above the modal at z-[60], inside the same portal root */}
      {confirmDelete && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setConfirmDelete(false)}
          />
          <div className="relative w-full max-w-sm mx-4 rounded-xl bg-[#0e0e12] border border-border shadow-2xl p-6">
            <p className="text-[14px] font-medium mb-1">{t('noteView.deleteConfirmTitle')}</p>
            <p className="text-[13px] text-muted-foreground/50 mb-6">
              {t('noteView.deleteConfirmDesc')}
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className="text-[13px] text-muted-foreground/50 hover:text-muted-foreground transition-colors"
              >
                {t('noteView.cancel')}
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="px-4 py-1.5 rounded-lg bg-destructive text-destructive-foreground text-[13px] font-medium hover:bg-destructive/90 transition-colors"
              >
                {t('noteView.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>,
    document.body,
  )
}

export default NoteViewModal
