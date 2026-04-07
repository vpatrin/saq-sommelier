import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import EmptyState from './EmptyState'

describe('EmptyState', () => {
  it('renders title and icon', () => {
    render(<EmptyState icon={<span data-testid="icon">X</span>} title="Nothing here" />)
    expect(screen.getByText('Nothing here')).toBeInTheDocument()
    expect(screen.getByTestId('icon')).toBeInTheDocument()
  })

  it('renders description when provided', () => {
    render(<EmptyState icon={<span>X</span>} title="Empty" description="Try adding one" />)
    expect(screen.getByText('Try adding one')).toBeInTheDocument()
  })

  it('omits description when prop is not provided', () => {
    render(<EmptyState icon={<span>X</span>} title="Empty" />)
    expect(screen.queryByText('Try adding one')).not.toBeInTheDocument()
  })

  it('calls cta.onClick when the CTA button is clicked', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn()
    render(<EmptyState icon={<span>X</span>} title="Empty" cta={{ label: 'Add', onClick }} />)
    await user.click(screen.getByRole('button', { name: 'Add' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('renders both primary and secondary CTAs', () => {
    render(
      <EmptyState
        icon={<span>X</span>}
        title="Empty"
        cta={{ label: 'Primary', onClick: vi.fn() }}
        secondaryCta={{ label: 'Secondary', onClick: vi.fn() }}
      />,
    )
    expect(screen.getByRole('button', { name: 'Primary' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Secondary' })).toBeInTheDocument()
  })
})
