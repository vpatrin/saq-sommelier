import { useCallback } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

const NAV_ITEMS = [
  { to: '/chat', label: 'Chat' },
  { to: '/search', label: 'Search' },
  { to: '/watches', label: 'My Watches' },
  { to: '/stores', label: 'My Stores' },
]

function AppShell() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const handleLogout = useCallback(() => {
    logout()
    navigate('/', { replace: true })
  }, [logout, navigate])

  return (
    <div className="h-screen bg-background text-foreground flex">
      {/* Sidebar */}
      <aside className="w-60 shrink-0 border-r border-border bg-sidebar text-sidebar-foreground flex flex-col h-full">
        {/* Brand */}
        <div className="p-4 border-b border-sidebar-border">
          <Link to="/chat" className="text-lg font-mono font-bold text-primary">
            Coupette
          </Link>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2 flex flex-col gap-0.5">
          {NAV_ITEMS.map(({ to, label }) => {
            const active =
              location.pathname === to ||
              (to === '/stores' && location.pathname === '/stores/nearby')
            return (
              <Link
                key={to}
                to={to}
                className={`block px-3 py-2 text-sm font-mono transition-colors ${
                  active
                    ? 'bg-sidebar-accent text-sidebar-accent-foreground font-bold'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent/50'
                }`}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom section */}
        <div className="p-4 border-t border-sidebar-border flex flex-col gap-3">
          <a
            href={`https://t.me/${BOT_USERNAME}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground hover:text-primary font-mono"
          >
            @{BOT_USERNAME}
          </a>
          <div className="flex items-center justify-between">
            <span className="text-sm font-mono truncate">{user?.first_name}</span>
            <Button variant="ghost" size="xs" onClick={handleLogout}>
              Logout
            </Button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 min-w-0 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}

export default AppShell
