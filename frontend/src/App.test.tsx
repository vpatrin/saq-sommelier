import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect } from 'vitest'
import { AuthProvider } from '@/contexts/AuthContext'
import './i18n'
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
  it('renders without crashing on /', () => {
    const { container } = renderApp('/')
    expect(container.firstChild).toBeTruthy()
  })
})
