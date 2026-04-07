import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import '../i18n'
import type { ProductOut } from '@/lib/types'
import WineCard from './WineCard'

function product(overrides: Partial<ProductOut> = {}): ProductOut {
  return {
    sku: 'SKU001',
    name: 'Château Test',
    category: 'Vin rouge',
    country: 'France',
    region: 'Bordeaux',
    size: '750 ml',
    price: '24.95',
    url: 'https://saq.com/SKU001',
    online_availability: true,
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
  } as ProductOut
}

describe('WineCard', () => {
  it('renders wine name and vintage', () => {
    render(<WineCard product={product()} />)
    expect(screen.getByText(/Château Test/)).toBeInTheDocument()
    expect(screen.getByText(/2021/)).toBeInTheDocument()
  })

  it('renders price', () => {
    render(<WineCard product={product()} />)
    expect(screen.getByText('24.95 $')).toBeInTheDocument()
  })

  it('hides price when null', () => {
    render(<WineCard product={product({ price: null })} />)
    expect(screen.queryByText(/\d+\.\d+ \$/)).not.toBeInTheDocument()
  })

  it('renders origin from region + country', () => {
    render(<WineCard product={product()} />)
    expect(screen.getByText('Bordeaux, France')).toBeInTheDocument()
  })

  it('renders grape variety', () => {
    render(<WineCard product={product()} />)
    expect(screen.getByText('Merlot')).toBeInTheDocument()
  })

  it('hides grape when null', () => {
    render(<WineCard product={product({ grape: null })} />)
    expect(screen.queryByText('Merlot')).not.toBeInTheDocument()
  })

  it('renders colored dot for Vin rouge category', () => {
    const { container } = render(<WineCard product={product({ category: 'Vin rouge' })} />)
    const dot = container.querySelector('.bg-red-500\\/80')
    expect(dot).toBeInTheDocument()
  })

  it('renders reason when provided', () => {
    render(<WineCard product={product()} reason="Great with steak" />)
    expect(screen.getByText('Great with steak')).toBeInTheDocument()
  })

  it('renders name as link when url present', () => {
    render(<WineCard product={product()} />)
    const link = screen.getByRole('link', { name: /Château Test/ })
    expect(link).toHaveAttribute('href', 'https://saq.com/SKU001')
    expect(link).toHaveAttribute('target', '_blank')
  })

  it('renders name as plain text when url is null', () => {
    render(<WineCard product={product({ url: null })} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
    expect(screen.getByText(/Château Test/)).toBeInTheDocument()
  })

  it('renders user rating when provided', () => {
    render(<WineCard product={product()} userRating={{ rating: 88, note_id: 1 }} />)
    expect(screen.getByText(/88/)).toBeInTheDocument()
  })
})
