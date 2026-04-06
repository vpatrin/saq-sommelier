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
    <div className="border-border hover:border-primary/20 relative h-[160px] overflow-hidden rounded-xl border bg-white/[0.025] transition-colors">
      {/* Warm gradient overlay */}
      <div className="from-primary/[0.02] pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br to-transparent" />

      <div className="relative flex h-full flex-col justify-between px-[18px] py-3">
        {/* Top: dot + name + price */}
        <div className="flex items-start gap-2.5">
          {dotColor && (
            <span className={`mt-[5px] h-2 w-2 flex-shrink-0 rounded-full ${dotColor}`} />
          )}
          <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
            <p className="line-clamp-2 min-w-0 flex-1 text-[14px] leading-snug font-medium">
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
              <p className="text-primary/90 flex-shrink-0 font-mono text-[18px] leading-none font-light whitespace-nowrap">
                {product.price} $
              </p>
            )}
          </div>
        </div>

        {/* Middle: region + grapes + user rating */}
        <div className="ml-[18px] flex min-w-0 flex-col gap-1">
          {origin && (
            <span
              className="text-muted-foreground inline-block max-w-full self-start truncate rounded border border-white/[0.06] bg-white/[0.04] px-2 py-0.5 text-[10px]"
              title={origin}
            >
              {origin}
            </span>
          )}
          {product.grape && (
            <p
              className="text-muted-foreground/50 truncate font-mono text-[10px]"
              title={product.grape}
            >
              {product.grape}
            </p>
          )}
          {userRating && (
            <p className="text-primary/70 font-mono text-[11px]">
              {t('wineCard.yourRating', { rating: userRating.rating })}
            </p>
          )}
        </div>

        {/* Reason / tasting note */}
        {reason && (
          <p className="text-muted-foreground border-border line-clamp-2 border-t pt-2 text-[12px] leading-snug font-light">
            {reason}
          </p>
        )}

        {/* Bottom row: availability left, user rating + watch right */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-2">
            {hasOnline && (
              <span className="text-[10px] text-green-500">{t('availability.online')}</span>
            )}
            {hasOnline && storeNode && (
              <span className="text-muted-foreground/50 text-[10px]">·</span>
            )}
            {storeNode}
          </div>
          {watchSlot}
        </div>
      </div>
    </div>
  )
}

export default WineCard
