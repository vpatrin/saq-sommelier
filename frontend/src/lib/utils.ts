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
