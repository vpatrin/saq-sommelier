import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect } from 'vitest'
import { AuthProvider } from '@/contexts/AuthContext'
import App from './App'

function renderApp(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  )
}

describe('App', () => {
  it('renders LandingPage at root route', () => {
    renderApp('/')
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
  })
})
