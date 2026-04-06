import { useState } from 'react'
import { X } from '@phosphor-icons/react'
import { useTranslation } from 'react-i18next'
import { useApiClient, ApiError } from '@/lib/api'
import { Button } from '@/components/ui/button'
import WineSearch from '@/components/WineSearch'
import type { TastingNoteOut, ProductOut } from '@/lib/types'

import { getBucket } from '@/lib/rating'

const DEFAULT_RATING = 87 // mid-range of bucket 4 (85–89 — "la cave commence ici")

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

interface TastingFormProps {
  // If provided, skip the wine search step (e.g. opened from a wine detail panel)
  initialProduct?: ProductOut
  // If provided, pre-fill fields and PATCH instead of POST
  noteId?: number
  initialRating?: number
  initialNotes?: string
  initialPairing?: string
  initialTastedAt?: string
  onSave: (note: TastingNoteOut) => void
  onCancel: () => void
}

function TastingForm({
  initialProduct,
  noteId,
  initialRating,
  initialNotes,
  initialPairing,
  initialTastedAt,
  onSave,
  onCancel,
}: TastingFormProps) {
  const apiClient = useApiClient()
  const { t } = useTranslation()

  const [product, setProduct] = useState<ProductOut | null>(initialProduct ?? null)

  const [rating, setRating] = useState(initialRating ?? DEFAULT_RATING)
  const bucket = getBucket(rating)
  const [notes, setNotes] = useState(initialNotes ?? '')
  const [pairing, setPairing] = useState(initialPairing ?? '')
  const [tastedAt, setTastedAt] = useState(initialTastedAt ?? todayIso())
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(false)

  const handleSubmit = async () => {
    if (saving || !product) return
    setSaving(true)
    setSaveError(false)
    try {
      const body = {
        rating,
        notes: notes.trim() || undefined,
        pairing: pairing.trim() || undefined,
        tasted_at: tastedAt,
      }
      const note = noteId
        ? await apiClient<TastingNoteOut>(`/tastings/${noteId}`, {
            method: 'PATCH',
            body: JSON.stringify(body),
          })
        : await apiClient<TastingNoteOut>('/tastings', {
            method: 'POST',
            body: JSON.stringify({ sku: product.sku, ...body }),
          })
      // Response has no product join — patch denormalized fields from the selected product
      onSave({
        ...note,
        product_name: product.name ?? product.sku,
        product_category: product.category,
        product_region: product.region,
        product_grape: product.grape,
        product_price: product.price ?? null,
      })
    } catch (err) {
      setSaveError(true)
      console.error('Save tasting failed', err instanceof ApiError ? err.detail : err)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="pt-1">
      {/* Wine picker — search when no product selected, chip when one is */}
      <div className="mb-4">
        <p className="text-muted-foreground/40 mb-1.5 font-mono text-[10px] tracking-widest uppercase">
          {t('tastingForm.wine')}
        </p>
        {product ? (
          <div className="border-border flex items-center justify-between gap-2 rounded-lg border bg-white/[0.04] px-3 py-2">
            <p className="truncate text-[13px] font-medium">{product.name ?? product.sku}</p>
            {/* In edit mode (noteId set) the wine is immutable — no X */}
            {!noteId && (
              <button
                type="button"
                onClick={() => setProduct(null)}
                className="text-muted-foreground/50 hover:text-foreground flex h-5 w-5 shrink-0 items-center justify-center rounded transition-colors"
                aria-label={t('tastingForm.changeWine')}
              >
                <X size={12} weight="bold" />
              </button>
            )}
          </div>
        ) : (
          <WineSearch onSelect={setProduct} onCancel={onCancel} />
        )}
      </div>

      {product && (
        <>
          <div className="mb-4">
            <p className="text-muted-foreground/40 mb-2 font-mono text-[10px] tracking-widest uppercase">
              {t('tastingForm.rating')}
            </p>
            <div className="flex items-center gap-3">
              <span className={`w-8 shrink-0 font-mono text-[18px] font-medium ${bucket.color}`}>
                {rating}
              </span>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={rating}
                onChange={(e) => setRating(Number(e.target.value))}
                className="accent-primary h-1 flex-1 cursor-pointer"
              />
              <span className="text-muted-foreground/40 shrink-0 font-mono text-[11px]">100</span>
            </div>
            <p className="text-muted-foreground/50 mt-1.5 text-[11px] italic">
              {bucket.stars} · {bucket.description}
            </p>
          </div>

          <div className="mb-3">
            <p className="text-muted-foreground/40 mb-1.5 font-mono text-[10px] tracking-widest uppercase">
              {t('tastingForm.notes')}
            </p>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder={t('tastingForm.notesPlaceholder')}
              maxLength={5000}
              rows={3}
              className="border-border placeholder:text-muted-foreground/40 focus:border-primary/30 w-full resize-none rounded-lg border bg-white/[0.04] px-3 py-2 text-[13px] transition-colors focus:outline-none"
            />
          </div>

          <div className="mb-3">
            <p className="text-muted-foreground/40 mb-1.5 font-mono text-[10px] tracking-widest uppercase">
              {t('tastingForm.pairing')}
            </p>
            <textarea
              value={pairing}
              onChange={(e) => setPairing(e.target.value)}
              placeholder={t('tastingForm.pairingPlaceholder')}
              maxLength={1000}
              rows={2}
              className="border-border placeholder:text-muted-foreground/40 focus:border-primary/30 w-full resize-none rounded-lg border bg-white/[0.04] px-3 py-2 text-[13px] transition-colors focus:outline-none"
            />
          </div>

          <div className="mb-4">
            <p className="text-muted-foreground/40 mb-1.5 font-mono text-[10px] tracking-widest uppercase">
              {t('tastingForm.date')}
            </p>
            <input
              type="date"
              value={tastedAt}
              onChange={(e) => setTastedAt(e.target.value)}
              className="border-border focus:border-primary/30 rounded-lg border bg-white/[0.04] px-3 py-1.5 text-[13px] transition-colors focus:outline-none"
            />
          </div>

          <div className="mt-2 flex items-center justify-end gap-4">
            {saveError && (
              <p className="text-destructive mr-auto text-[11px]">
                {t('tastingForm.failedToSave')}{' '}
                <button type="button" className="underline" onClick={handleSubmit}>
                  {t('tastingForm.retry')}
                </button>
              </p>
            )}
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="text-muted-foreground/50 hover:text-muted-foreground text-[13px] transition-colors disabled:opacity-40"
            >
              {t('tastingForm.cancel')}
            </button>
            <Button size="sm" onClick={handleSubmit} disabled={saving}>
              {saving ? t('tastingForm.saving') : t('tastingForm.save')}
            </Button>
          </div>
        </>
      )}

      {/* Cancel-only footer shown while searching for a wine */}
      {!product && (
        <div className="mt-2 flex justify-end">
          <button
            type="button"
            onClick={onCancel}
            className="text-muted-foreground/50 hover:text-muted-foreground text-[13px] transition-colors"
          >
            {t('tastingForm.cancel')}
          </button>
        </div>
      )}
    </div>
  )
}

export default TastingForm
