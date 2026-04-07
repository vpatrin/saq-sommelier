import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi } from 'vitest'
import '../i18n'
import UserMenu from './UserMenu'

describe('UserMenu', () => {
  it('renders display name initial in avatar', () => {
    render(<UserMenu displayName="Victor" onLogout={vi.fn()} />)
    expect(screen.getByText('V')).toBeInTheDocument()
  })

  it('renders ? when display name is null', () => {
    render(<UserMenu displayName={null} onLogout={vi.fn()} />)
    expect(screen.getByText('?')).toBeInTheDocument()
  })

  it('calls onLogout when logout button clicked', async () => {
    const user = userEvent.setup()
    const onLogout = vi.fn()
    render(<UserMenu displayName="Victor" onLogout={onLogout} />)
    // i18n key: userMenu.logout → "Sign out" (en) / "Déconnexion" (fr)
    await user.click(screen.getByText(/sign out|déconnexion/i))
    expect(onLogout).toHaveBeenCalledOnce()
  })

  it('calls onNavigate with /settings when settings clicked', async () => {
    const user = userEvent.setup()
    const onNavigate = vi.fn()
    render(<UserMenu displayName="Victor" onLogout={vi.fn()} onNavigate={onNavigate} />)
    await user.click(screen.getByText(/settings|réglages/i))
    expect(onNavigate).toHaveBeenCalledWith('/settings')
  })

  it('shows admin link when role is admin', () => {
    render(<UserMenu displayName="Victor" role="admin" onLogout={vi.fn()} onNavigate={vi.fn()} />)
    // i18n key: nav.admin → "Console"
    expect(screen.getByText(/console/i)).toBeInTheDocument()
  })

  it('hides admin link for regular users', () => {
    render(<UserMenu displayName="Victor" role="user" onLogout={vi.fn()} />)
    expect(screen.queryByText(/console/i)).not.toBeInTheDocument()
  })
})
