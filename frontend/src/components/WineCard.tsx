import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { formatOrigin, CATEGORY_DOT } from '@/lib/utils'
import type { ProductOut, TastingRatingOut } from '@/lib/types'

interface WineCardProps {
  product: ProductOut
  reason?: string
  storeNames?: Map<string, string>
  watchSlot?: ReactNode
  userRating?: TastingRatingOut | null
}

function WineCard({ product, reason, storeNames, watchSlot, userRating }: WineCardProps) {
  const { t } = useTranslation()
  const origin = formatOrigin(product)
  const hasOnline = product.online_availability === true
  const storeAvail = product.store_availability ?? []

  const matchingIds = storeNames ? storeAvail.filter((id) => storeNames.has(id)) : []
  const hasStores = storeNames && storeNames.size > 0

  const storeText =
    matchingIds.length === 1
      ? t('availability.atStore', { store: storeNames?.get(matchingIds[0]) })
      : t('availability.inYourStores', { count: matchingIds.length })

  const storeNode = hasStores ? (
    matchingIds.length > 0 ? (
      <span className="text-[10px] text-green-500">{storeText}</span>
    ) : null
  ) : storeAvail.length > 0 ? (
    <span className="text-[10px] text-green-500">
      {t('availability.inStores', { count: storeAvail.length })}
    </span>
  ) : null

  const dotColor = product.category
    ? (CATEGORY_DOT[product.category] ?? 'bg-muted-foreground/40')
    : null

  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-white/[0.025] transition-colors hover:border-primary/20 h-[160px]">
      {/* Warm gradient overlay */}
      <div className="pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br from-primary/[0.02] to-transparent" />

      <div className="relative px-[18px] py-3 h-full flex flex-col justify-between">
        {/* Top: dot + name + price */}
        <div className="flex items-start gap-2.5">
          {dotColor && (
            <span className={`mt-[5px] w-2 h-2 rounded-full flex-shrink-0 ${dotColor}`} />
          )}
          <div className="flex items-start justify-between gap-3 flex-1 min-w-0">
            <p className="text-[14px] font-medium leading-snug min-w-0 flex-1 line-clamp-2">
              {product.url ? (
                <a
                  href={product.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hover:text-primary transition-colors"
                >
                  {product.name}
                  {product.vintage && ` ${product.vintage}`}
                </a>
              ) : (
                <>
                  {product.name}
                  {product.vintage && ` ${product.vintage}`}
                </>
              )}
            </p>
            {product.price && (
              <p className="font-mono text-[18px] font-light text-primary/90 leading-none whitespace-nowrap flex-shrink-0">
                {product.price} $
              </p>
            )}
          </div>
        </div>

        {/* Middle: region + grapes */}
        <div className="ml-[18px] flex flex-col gap-1 min-w-0">
          {origin && (
            <span
              className="text-[10px] px-2 py-0.5 rounded border bg-white/[0.04] text-muted-foreground border-white/[0.06] truncate inline-block self-start max-w-full"
              title={origin}
            >
              {origin}
            </span>
          )}
          {product.grape && (
            <p
              className="font-mono text-[10px] text-muted-foreground/50 truncate"
              title={product.grape}
            >
              {product.grape}
            </p>
          )}
        </div>

        {/* Reason / tasting note */}
        {reason && (
          <p className="text-[12px] font-light text-muted-foreground leading-snug line-clamp-2 border-t border-border pt-2">
            {reason}
          </p>
        )}

        {/* Bottom row: availability left, user rating + watch right */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            {hasOnline && (
              <span className="text-[10px] text-green-500">{t('availability.online')}</span>
            )}
            {hasOnline && storeNode && (
              <span className="text-[10px] text-muted-foreground/50">·</span>
            )}
            {storeNode}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {userRating && (
              <span className="font-mono text-[10px] text-muted-foreground/60">
                {t('wineCard.yourRating', { rating: userRating.rating })}
              </span>
            )}
            {watchSlot}
          </div>
        </div>
      </div>
    </div>
  )
}

export default WineCard
