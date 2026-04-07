import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { TFunction } from 'i18next'
import type { ProductOut } from '@/lib/types'
import { formatOrigin, CATEGORY_DOT, timeAgoPrecise, timeAgo } from './utils'

function product(overrides: Partial<ProductOut> = {}): ProductOut {
  return { country: null, region: null, ...overrides } as ProductOut
}

describe('formatOrigin', () => {
  it('returns region + country when both present and different', () => {
    expect(formatOrigin(product({ region: 'Bordeaux', country: 'France' }))).toBe(
      'Bordeaux, France',
    )
  })

  it('returns region alone when same as country', () => {
    expect(formatOrigin(product({ region: 'France', country: 'France' }))).toBe('France')
  })

  it('returns country when region is null', () => {
    expect(formatOrigin(product({ country: 'Italy' }))).toBe('Italy')
  })

  it('returns region when country is null', () => {
    expect(formatOrigin(product({ region: 'Toscana' }))).toBe('Toscana')
  })

  it('returns empty string when both null', () => {
    expect(formatOrigin(product())).toBe('')
  })

  it('deduplicates repeated region segments', () => {
    expect(formatOrigin(product({ region: 'Bourgogne, Bourgogne', country: 'France' }))).toBe(
      'Bourgogne, France',
    )
  })
})

describe('CATEGORY_DOT', () => {
  it('maps Vin rouge to red', () => {
    expect(CATEGORY_DOT['Vin rouge']).toBe('bg-red-500/80')
  })

  it('maps sparkling categories to the same color', () => {
    expect(CATEGORY_DOT['Champagne']).toBe(CATEGORY_DOT['Vin mousseux'])
  })

  it('returns undefined for unmapped category', () => {
    expect(CATEGORY_DOT['Bière']).toBeUndefined()
  })
})

describe('timeAgoPrecise', () => {
  const NOW = new Date('2026-01-15T12:00:00Z').getTime()
  const tMock = vi.fn((key: string, opts?: { count: number }) => `${key}:${opts?.count}`)
  const t = tMock as unknown as TFunction

  beforeEach(() => {
    tMock.mockClear()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })
  afterEach(() => vi.useRealTimers())

  it('returns minutes for < 60 min', () => {
    timeAgoPrecise('2026-01-15T11:30:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.minutesAgoPrecise', { count: 30 })
  })

  it('clamps to 1 minute minimum', () => {
    timeAgoPrecise('2026-01-15T11:59:50Z', t)
    expect(tMock).toHaveBeenCalledWith('time.minutesAgoPrecise', { count: 1 })
  })

  it('returns hours for < 24h', () => {
    timeAgoPrecise('2026-01-15T06:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.hoursAgoPrecise', { count: 6 })
  })

  it('returns days for < 30d', () => {
    timeAgoPrecise('2026-01-10T12:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.daysAgoPrecise', { count: 5 })
  })

  it('returns months for < 12mo', () => {
    timeAgoPrecise('2025-10-15T12:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.monthsAgoPrecise', { count: 3 })
  })

  it('returns years for >= 12mo', () => {
    timeAgoPrecise('2024-01-15T12:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.yearsAgoPrecise', { count: 2 })
  })
})

describe('timeAgo', () => {
  const NOW = new Date('2026-01-15T12:00:00Z').getTime()
  const tMock = vi.fn((key: string) => key)
  const t = tMock as unknown as TFunction

  beforeEach(() => {
    tMock.mockClear()
    vi.useFakeTimers()
    vi.setSystemTime(NOW)
  })
  afterEach(() => vi.useRealTimers())

  it('returns justNow for < 2 min', () => {
    timeAgo('2026-01-15T11:59:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.justNow')
  })

  it('returns today for < 24h', () => {
    timeAgo('2026-01-15T06:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.today')
  })

  it('returns yesterday for < 48h', () => {
    timeAgo('2026-01-14T06:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.yesterday')
  })

  it('returns pastWeek for < 7d', () => {
    timeAgo('2026-01-10T12:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.pastWeek')
  })

  it('returns pastMonth for < 30d', () => {
    timeAgo('2026-01-01T12:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.pastMonth')
  })

  it('returns pastYear for < 365d', () => {
    timeAgo('2025-06-15T12:00:00Z', t)
    expect(tMock).toHaveBeenCalledWith('time.pastYear')
  })

  it('returns formatted date for >= 1 year', () => {
    const result = timeAgo('2024-01-15T12:00:00Z', t)
    // Falls through to toLocaleDateString — tMock is not called with a time key
    expect(result).toContain('2024')
  })
})
