import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { ProtectedRoute } from './ProtectedRoute'

vi.mock('@/contexts/AuthContext', () => ({
  useAuth: vi.fn(),
}))

import { useAuth } from '@/contexts/AuthContext'
const mockUseAuth = vi.mocked(useAuth)

beforeEach(() => {
  localStorage.clear()
})

function renderProtected() {
  return render(
    <MemoryRouter initialEntries={['/protected']}>
      <Routes>
        <Route path="/" element={<div data-testid="home" />} />
        <Route path="/onboarding" element={<div data-testid="onboarding" />} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <div data-testid="protected-content">Secret</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('redirects to / when unauthenticated', () => {
    mockUseAuth.mockReturnValue({ token: null } as ReturnType<typeof useAuth>)
    renderProtected()
    expect(screen.getByTestId('home')).toBeInTheDocument()
  })

  it('redirects to /onboarding when authenticated but not onboarded', () => {
    mockUseAuth.mockReturnValue({ token: 'jwt.token.here' } as ReturnType<typeof useAuth>)
    renderProtected()
    expect(screen.getByTestId('onboarding')).toBeInTheDocument()
  })

  it('renders children when authenticated and onboarded', () => {
    mockUseAuth.mockReturnValue({ token: 'jwt.token.here' } as ReturnType<typeof useAuth>)
    localStorage.setItem('onboarded', '1')
    renderProtected()
    expect(screen.getByTestId('protected-content')).toBeInTheDocument()
  })
})
