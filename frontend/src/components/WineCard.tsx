import { useTranslation } from 'react-i18next'
import { formatOrigin } from '@/lib/utils'
import type { ProductOut } from '@/lib/types'

interface WineCardProps {
  product: ProductOut
  reason?: string
  /** Store ID → store name lookup. When provided, availability shows "At Store Name" / "In N of your stores". */
  storeNames?: Map<string, string>
  /** When true + storeNames provided, expands the list of matching store names below the availability line. */
  storesExpanded?: boolean
  /** Called when "In N of your stores" is clicked (only fires when 2+ stores match). */
  onToggleStores?: () => void
}

function WineCard({ product, reason, storeNames, storesExpanded, onToggleStores }: WineCardProps) {
  const { t } = useTranslation()
  const origin = formatOrigin(product)
  const details = [product.grape, origin, product.vintage].filter(Boolean).join(' · ')
  const hasOnline = product.online_availability === true
  const storeAvail = product.store_availability ?? []

  // Cross-reference with user's saved stores when available
  const matchingIds = storeNames ? storeAvail.filter((id) => storeNames.has(id)) : []
  const hasStores = storeNames && storeNames.size > 0
  const canExpand = matchingIds.length > 1 && onToggleStores

  const storeText =
    matchingIds.length === 1
      ? t('availability.atStore', { store: storeNames?.get(matchingIds[0]) })
      : t('availability.inYourStores', { count: matchingIds.length })

  const storeNode = hasStores ? (
    matchingIds.length > 0 ? (
      canExpand ? (
        <button
          type="button"
          className="text-xs text-green-500 hover:underline underline-offset-4 cursor-pointer"
          onClick={onToggleStores}
        >
          {storeText}
        </button>
      ) : (
        <span className="text-xs text-green-500">{storeText}</span>
      )
    ) : null
  ) : storeAvail.length > 0 ? (
    <span className="text-xs text-green-500">
      {t('availability.inStores', { count: storeAvail.length })}
    </span>
  ) : null

  return (
    <div className="flex-1 min-w-0">
      {/* Line 1: Name (links to SAQ) */}
      <p className="font-mono font-bold text-sm line-clamp-2">
        {product.url ? (
          <a
            href={product.url}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-primary"
          >
            {product.name}
          </a>
        ) : (
          product.name
        )}
      </p>

      {/* Line 2: Grape · Origin · Vintage */}
      {details && <p className="text-xs text-muted-foreground mt-0.5">{details}</p>}

      {/* Line 3: Price + availability */}
      <div className="flex items-center gap-3 mt-1">
        {product.price && (
          <span className="text-sm">
            {product.price} ${' '}
            {product.size && (
              <span className="text-muted-foreground text-xs">/ {product.size}</span>
            )}
          </span>
        )}
        {hasOnline && <span className="text-xs text-green-500">{t('availability.online')}</span>}
        {hasOnline && storeNode && <span className="text-xs text-muted-foreground">·</span>}
        {storeNode}
      </div>

      {/* Expanded store list */}
      {storesExpanded && matchingIds.length > 1 && (
        <ul className="text-muted-foreground text-xs ml-1 mt-1">
          {matchingIds.map((id) => (
            <li key={id}>{storeNames?.get(id)}</li>
          ))}
        </ul>
      )}

      {/* Reason (chat only) */}
      {reason && <p className="text-sm mt-2">{reason}</p>}
    </div>
  )
}

export default WineCard
