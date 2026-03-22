import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import type { ProductOut } from '@/lib/types'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/** Deduplicate "Bourgogne, Bourgogne" → "Bourgogne", then combine with country. */
export function formatOrigin(product: ProductOut): string {
  const region = product.region ? [...new Set(product.region.split(', '))].join(', ') : null
  if (region && product.country && region !== product.country) {
    return `${region}, ${product.country}`
  }
  return region || product.country || ''
}

import type { TFunction } from 'i18next'

export function timeAgo(dateStr: string, t: TFunction): string {
  const seconds = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000)
  if (seconds < 60) return t('time.justNow')
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return t('time.minutesAgo', { count: minutes })
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return t('time.hoursAgo', { count: hours })
  const days = Math.floor(hours / 24)
  if (days < 30) return t('time.daysAgo', { count: days })
  return new Date(dateStr).toLocaleDateString()
}
