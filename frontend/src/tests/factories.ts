import type { ProductOut, TastingNoteOut } from '@/lib/types'

export function product(overrides: Partial<ProductOut> = {}): ProductOut {
  return {
    sku: 'SKU001',
    name: 'Château Test',
    category: 'Vin rouge',
    country: 'France',
    region: 'Bordeaux',
    size: '750 ml',
    price: '24.95',
    url: 'https://saq.com/SKU001',
    online_availability: false,
    store_availability: [],
    rating: null,
    review_count: null,
    appellation: null,
    designation: null,
    classification: null,
    grape: 'Merlot',
    grape_blend: null,
    alcohol: '13.5%',
    sugar: null,
    producer: null,
    vintage: '2021',
    taste_tag: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

export function fakeNote(overrides: Partial<TastingNoteOut> = {}): TastingNoteOut {
  return {
    id: 1,
    sku: 'SKU001',
    rating: 87,
    notes: null,
    pairing: null,
    tasted_at: '2026-01-01',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    product_name: 'Château Test',
    product_image_url: null,
    product_category: 'Vin rouge',
    product_region: 'Bordeaux',
    product_grape: 'Merlot',
    product_price: '24.95',
    ...overrides,
  }
}
