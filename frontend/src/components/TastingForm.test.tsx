import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useApiClient, ApiError } from '@/lib/api'
import '../i18n'
import { product, fakeNote } from '@/tests/factories'
import TastingForm from './TastingForm'
import type { TastingNoteOut } from '@/lib/types'

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

// Stub WineSearch — its API calls are out of scope for TastingForm tests
vi.mock('@/components/WineSearch', () => ({
  default: ({ onCancel }: { onSelect: unknown; onCancel: () => void }) => (
    <button type="button" onClick={onCancel}>
      Cancel
    </button>
  ),
}))

const mockApiClient = vi.fn()

beforeEach(() => {
  mockApiClient.mockReset()
  vi.mocked(useApiClient).mockReturnValue(mockApiClient)
})

describe('TastingForm', () => {
  it('renders rating slider and impressions section when initialProduct provided', () => {
    render(<TastingForm initialProduct={product()} onSave={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByRole('slider')).toBeInTheDocument()
    expect(screen.getByText('Impressions')).toBeInTheDocument()
  })

  it('pre-fills rating and notes from initial values', () => {
    render(
      <TastingForm
        initialProduct={product()}
        initialRating={92}
        initialNotes="Lovely finish"
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    )
    expect(screen.getByRole('slider')).toHaveValue('92')
    expect(screen.getByDisplayValue('Lovely finish')).toBeInTheDocument()
  })

  it('calls onSave with correct sku and rating after successful POST', async () => {
    mockApiClient.mockResolvedValue(fakeNote({ rating: 87 }))
    const onSave = vi.fn()
    render(<TastingForm initialProduct={product()} onSave={onSave} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ sku: 'SKU001', rating: 87 }))
  })

  it('shows saving label and disables button while request is in flight', async () => {
    let resolve: (n: TastingNoteOut) => void
    const pending = new Promise<TastingNoteOut>((r) => {
      resolve = r
    })
    mockApiClient.mockReturnValue(pending)
    render(<TastingForm initialProduct={product()} onSave={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(await screen.findByRole('button', { name: /saving/i })).toBeDisabled()
    resolve!(fakeNote())
    // Drain the resolved promise so setSaving(false) runs inside act()
    await waitFor(() => expect(screen.getByRole('button', { name: /save/i })).toBeEnabled())
  })

  it('shows error message with retry when save fails', async () => {
    mockApiClient.mockRejectedValue(new ApiError(500, 'DB error'))
    render(<TastingForm initialProduct={product()} onSave={vi.fn()} onCancel={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    expect(await screen.findByText(/Couldn't save/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('calls onCancel when cancel is clicked', () => {
    const onCancel = vi.fn()
    render(<TastingForm initialProduct={product()} onSave={vi.fn()} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalledOnce()
  })

  it('hides rating and notes form when no initialProduct provided', () => {
    render(<TastingForm onSave={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.queryByRole('slider')).not.toBeInTheDocument()
    expect(screen.queryByText('Impressions')).not.toBeInTheDocument()
  })

  it('PATCHes existing note when noteId is provided', async () => {
    mockApiClient.mockResolvedValue(fakeNote({ id: 42, rating: 90 }))
    const onSave = vi.fn()
    render(
      <TastingForm
        noteId={42}
        initialProduct={product()}
        initialRating={90}
        onSave={onSave}
        onCancel={vi.fn()}
      />,
    )
    fireEvent.click(screen.getByRole('button', { name: /save/i }))
    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
    expect(mockApiClient).toHaveBeenCalledWith(
      '/tastings/42',
      expect.objectContaining({ method: 'PATCH' }),
    )
    // PATCH body omits sku (only POST includes it)
    const body = JSON.parse(mockApiClient.mock.calls[0][1].body)
    expect(body).not.toHaveProperty('sku')
  })

  it('hides change-wine button in edit mode', () => {
    render(
      <TastingForm noteId={42} initialProduct={product()} onSave={vi.fn()} onCancel={vi.fn()} />,
    )
    expect(screen.queryByRole('button', { name: /change wine/i })).not.toBeInTheDocument()
  })
})
