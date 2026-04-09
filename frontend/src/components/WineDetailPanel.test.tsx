import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { MemoryRouter } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import { useApiClient, ApiError } from '@/lib/api'
import { product } from '@/tests/factories'
import WineDetailPanel from './WineDetailPanel'

vi.mock('@/contexts/AuthContext', () => ({ useAuth: vi.fn() }))
vi.mock('@/lib/api', () => ({
  useApiClient: vi.fn(),
  ApiError: class ApiError extends Error {
    status: number
    detail: string
    constructor(status: number, detail: string) {
      super(detail)
      this.status = status
      this.detail = detail
    }
  },
}))

const mockApiClient = vi.fn()

function renderPanel(sku: string | null, onClose = vi.fn()) {
  return render(
    <MemoryRouter>
      <WineDetailPanel sku={sku} onClose={onClose} />
    </MemoryRouter>,
  )
}

function apiReturning(
  p: ReturnType<typeof product>,
  overrides?: { watchPost?: () => Promise<unknown> },
) {
  mockApiClient.mockImplementation((url: string, opts?: RequestInit) => {
    if (url.startsWith('/products/')) return Promise.resolve(p)
    if (url.includes('/watches') && opts?.method === 'POST')
      return overrides?.watchPost?.() ?? Promise.resolve({})
    if (url.includes('/watches')) return Promise.resolve([])
    if (url.includes('/stores/preferences')) return Promise.resolve([])
    return Promise.reject(new Error(`unexpected api call: ${url}`))
  })
}

beforeEach(() => {
  mockApiClient.mockReset()
  vi.mocked(useAuth).mockReturnValue({ user: { id: 1 } } as ReturnType<typeof useAuth>)
  vi.mocked(useApiClient).mockReturnValue(mockApiClient)
})

describe('WineDetailPanel', () => {
  it('renders wine name in heading when product loads', async () => {
    apiReturning(product())
    renderPanel('SKU001')
    expect(await screen.findByRole('heading', { level: 2 })).toHaveTextContent('Château Test')
  })

  it('renders price with currency symbol', async () => {
    apiReturning(product())
    renderPanel('SKU001')
    expect(await screen.findByText('24.95 $')).toBeInTheDocument()
  })

  it('renders grape variety when present', async () => {
    apiReturning(product())
    renderPanel('SKU001')
    expect(await screen.findByText('Merlot')).toBeInTheDocument()
  })

  it('omits grape section when grape is null', async () => {
    apiReturning(product({ grape: null }))
    renderPanel('SKU001')
    // Wait for loaded state (h2 present), then assert absence
    await screen.findByRole('heading', { level: 2 })
    expect(screen.queryByText('Grapes')).not.toBeInTheDocument()
  })

  it('calls onClose when close button is clicked', () => {
    apiReturning(product())
    const onClose = vi.fn()
    renderPanel('SKU001', onClose)
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('shows error message with retry when product fetch fails', async () => {
    mockApiClient.mockImplementation((url: string) => {
      if (url.startsWith('/products/')) return Promise.reject(new ApiError(500, 'Server error'))
      return Promise.resolve([])
    })
    renderPanel('SKU001')
    await waitFor(() => expect(screen.getByText(/Server error/)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('optimistically switches to Watching on watch click', async () => {
    apiReturning(product())
    renderPanel('SKU001')
    await screen.findByRole('heading', { level: 2 })
    fireEvent.click(screen.getByRole('button', { name: /watch$/i }))
    expect(await screen.findByRole('button', { name: /watching/i })).toBeInTheDocument()
  })

  it('rolls back to Watch when watch API call fails', async () => {
    apiReturning(product(), {
      watchPost: () => Promise.reject(new Error('network')),
    })
    renderPanel('SKU001')
    await screen.findByRole('heading', { level: 2 })
    fireEvent.click(screen.getByRole('button', { name: /watch$/i }))
    // During the request, button shows "..." (busy state masks the optimistic text)
    expect(screen.getByRole('button', { name: '...' })).toBeDisabled()
    // After rejection settles: rolls back to Watch
    await waitFor(() => expect(screen.getByRole('button', { name: /watch$/i })).toBeInTheDocument())
  })
})
