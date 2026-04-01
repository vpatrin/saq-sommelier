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

// One color per wine group — all subcategories inherit their group's color.
// Only the 6 groups shown as chips in Search are mapped; everything else gets no dot.
const FORTIFIED_COLOR = 'bg-amber-800/80'
const SPARKLING_COLOR = 'bg-stone-200/80'

export const CATEGORY_DOT: Record<string, string> = {
  // Rouge
  'Vin rouge': 'bg-red-500/80',
  // Blanc
  'Vin blanc': 'bg-yellow-400/80',
  // Rosé
  'Vin rosé': 'bg-pink-400/80',
  'Vin rosé effervescent': 'bg-pink-400/80',
  // Champagne & Mousseux
  Champagne: SPARKLING_COLOR,
  'Vin mousseux': SPARKLING_COLOR,
  'Vin blanc effervescent': SPARKLING_COLOR,
  // Fortifié — all subcategories inherit tuilé/brun
  Porto: FORTIFIED_COLOR,
  Madère: FORTIFIED_COLOR,
  Xérès: FORTIFIED_COLOR,
  Marsala: FORTIFIED_COLOR,
  Sauternes: FORTIFIED_COLOR,
  Muscat: FORTIFIED_COLOR,
  Pineau: FORTIFIED_COLOR,
  Banyuls: FORTIFIED_COLOR,
  Maury: FORTIFIED_COLOR,
  Rivesaltes: FORTIFIED_COLOR,
  Macvin: FORTIFIED_COLOR,
  Floc: FORTIFIED_COLOR,
  Moscatel: FORTIFIED_COLOR,
  Montilla: FORTIFIED_COLOR,
  'Vin de dessert': FORTIFIED_COLOR,
  'Vin de glace': FORTIFIED_COLOR,
  'Vin fortifié': FORTIFIED_COLOR,
  'Vin doux naturel': FORTIFIED_COLOR,
  // Saké
  Saké: 'bg-emerald-700/80',
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
