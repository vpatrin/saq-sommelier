import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import FilterChips from './FilterChips'

const OPTIONS = [
  { label: 'Rouge', value: 'red' },
  { label: 'Blanc', value: 'white' },
  { label: 'Rosé', value: 'rose' },
]

describe('FilterChips', () => {
  it('renders all options as buttons', () => {
    render(<FilterChips options={OPTIONS} value="" onChange={vi.fn()} />)
    expect(screen.getAllByRole('button')).toHaveLength(3)
    expect(screen.getByText('Rouge')).toBeInTheDocument()
    expect(screen.getByText('Blanc')).toBeInTheDocument()
    expect(screen.getByText('Rosé')).toBeInTheDocument()
  })

  it('calls onChange with value when clicking inactive chip', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<FilterChips options={OPTIONS} value="" onChange={onChange} />)
    await user.click(screen.getByText('Rouge'))
    expect(onChange).toHaveBeenCalledWith('red')
  })

  it('calls onChange with empty string when clicking active chip (deselect)', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    render(<FilterChips options={OPTIONS} value="red" onChange={onChange} />)
    await user.click(screen.getByText('Rouge'))
    expect(onChange).toHaveBeenCalledWith('')
  })

  it('renders no buttons when options array is empty', () => {
    const { container } = render(<FilterChips options={[]} value="" onChange={vi.fn()} />)
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })
})
