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
      <div className="border-border relative mx-4 flex max-h-[90vh] w-full max-w-lg flex-col rounded-xl border bg-[#0e0e12] shadow-2xl">
        {/* Top bar */}
        <div className="border-border flex shrink-0 items-center justify-between border-b px-5 py-3.5">
          <button
            type="button"
            onClick={onClose}
            className="text-muted-foreground/50 hover:text-muted-foreground flex items-center gap-1.5 text-[12px] transition-colors"
          >
            <ArrowLeft size={13} weight="bold" />
            {t('nav.journal')}
          </button>
          {mode === 'view' && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setMode('edit')}
                className="text-muted-foreground/40 hover:text-foreground flex h-7 w-7 items-center justify-center rounded-md transition-all hover:bg-white/[0.04]"
                aria-label={t('noteView.edit')}
              >
                <PencilSimple size={14} />
              </button>
              <button
                type="button"
                onClick={() => setConfirmDelete(true)}
                className="text-muted-foreground/40 hover:text-destructive hover:bg-destructive/10 flex h-7 w-7 items-center justify-center rounded-md transition-all"
                aria-label={t('noteView.delete')}
              >
                <Trash size={14} />
              </button>
            </div>
          )}
          {mode === 'edit' && <p className="text-[13px] font-medium">{t('journal.editNote')}</p>}
        </div>

        {/* Scrollable content */}
        <div className="flex flex-col gap-4 overflow-y-auto p-5">
          {mode === 'view' ? (
            <>
              {/* Wine header — styled like WineCard but with rating instead of price */}
              <div
                className="border-border flex flex-col justify-between gap-3 rounded-xl border bg-white/[0.025] px-[18px] py-3"
                style={{ borderLeft: '3px solid rgba(200,146,72,0.35)' }}
              >
                {/* Top: dot + name + rating */}
                <div className="flex items-start gap-2.5">
                  {dotColor && (
                    <span className={`mt-[5px] h-2 w-2 flex-shrink-0 rounded-full ${dotColor}`} />
                  )}
                  <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
                    <a
                      href={saqUrl(currentNote.sku)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:text-primary line-clamp-2 text-[14px] leading-snug font-medium transition-colors"
                    >
                      {currentNote.product_name ?? currentNote.sku}
                    </a>
                    <p className="text-primary/90 flex-shrink-0 font-mono text-[18px] leading-none font-light whitespace-nowrap">
                      {currentNote.rating}{' '}
                      <span className="text-muted-foreground/40 text-[12px]">/ 100</span>
                    </p>
                  </div>
                </div>

                {/* Middle: region pill + grapes */}
                {(origin || product?.grape) && (
                  <div className="ml-[18px] flex min-w-0 flex-col gap-1">
                    {origin && (
                      <span className="text-muted-foreground inline-block max-w-full self-start truncate rounded border border-white/[0.06] bg-white/[0.04] px-2 py-0.5 text-[10px]">
                        {origin}
                      </span>
                    )}
                    {product?.grape && (
                      <p className="text-muted-foreground/50 truncate font-mono text-[10px]">
                        {product.grape}
                      </p>
                    )}
                  </div>
                )}

                {/* Bottom: availability + watch */}
                <div className="ml-[18px] flex items-center justify-between gap-3">
                  <div className="flex min-w-0 items-center gap-2">
                    {product?.online_availability && (
                      <span className="text-[10px] text-green-500">{t('availability.online')}</span>
                    )}
                    {product?.online_availability &&
                      (product?.store_availability?.length ?? 0) > 0 && (
                        <span className="text-muted-foreground/50 text-[10px]">·</span>
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
                    className={`rounded-lg border px-3 py-1 text-[11px] transition-colors disabled:opacity-40 ${
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
                <div className="mb-1.5 flex items-center gap-3">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/[0.06]">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${currentNote.rating}%`,
                        background: ratingColor(currentNote.rating),
                      }}
                    />
                  </div>
                </div>
                <p className="text-muted-foreground/50 text-[11px] italic">{bucket.description}</p>
              </div>

              {/* Impressions */}
              {currentNote.notes && (
                <div>
                  <p className="text-muted-foreground/40 mb-2 font-mono text-[10px] tracking-widest uppercase">
                    {t('tastingForm.notes')}
                  </p>
                  <p className="text-muted-foreground/80 text-[14px] leading-relaxed font-light">
                    {currentNote.notes}
                  </p>
                </div>
              )}

              {/* Pairing */}
              {currentNote.pairing && (
                <div>
                  <p className="text-muted-foreground/40 mb-2 font-mono text-[10px] tracking-widest uppercase">
                    {t('tastingForm.pairing')}
                  </p>
                  <p className="text-muted-foreground/80 text-[14px] leading-relaxed font-light">
                    {currentNote.pairing}
                  </p>
                </div>
              )}

              {/* Date */}
              <p className="text-muted-foreground/30 border-border border-t pt-2 font-mono text-[11px]">
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
          <div className="border-border relative mx-4 w-full max-w-sm rounded-xl border bg-[#0e0e12] p-6 shadow-2xl">
            <p className="mb-1 text-[14px] font-medium">{t('noteView.deleteConfirmTitle')}</p>
            <p className="text-muted-foreground/50 mb-6 text-[13px]">
              {t('noteView.deleteConfirmDesc')}
            </p>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setConfirmDelete(false)}
                className="text-muted-foreground/50 hover:text-muted-foreground text-[13px] transition-colors"
              >
                {t('noteView.cancel')}
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirm}
                className="bg-destructive text-destructive-foreground hover:bg-destructive/90 rounded-lg px-4 py-1.5 text-[13px] font-medium transition-colors"
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
