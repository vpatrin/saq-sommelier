import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Link, useNavigate } from 'react-router'

const BOT_USERNAME = import.meta.env.VITE_TELEGRAM_BOT_USERNAME as string

function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/', { replace: true })
  }

  return (
    <div className="min-h-screen bg-background text-foreground p-8">
      <div className="max-w-2xl mx-auto flex flex-col gap-6">
        <h1 className="text-3xl font-mono font-bold">
          Welcome, {user?.first_name}
        </h1>

        <nav className="flex gap-4">
          <Link
            to="/watches"
            className="text-primary font-mono underline underline-offset-4"
          >
            My Watches
          </Link>
          <Link
            to="/stores"
            className="text-primary font-mono underline underline-offset-4"
          >
            My Stores
          </Link>
        </nav>

        <div className="border border-border p-4 flex flex-col gap-2">
          <p className="font-mono font-bold">Enable Telegram alerts</p>
          <p className="text-sm text-muted-foreground">
            Get notified when your watched wines become available online or in store.
          </p>
          <a
            href={`https://t.me/${BOT_USERNAME}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm"
          >
            Open <span className="text-primary font-mono underline underline-offset-4">@{BOT_USERNAME}</span>
          </a>
        </div>

        <div>
          <Button variant="outline" onClick={handleLogout}>
            Logout
          </Button>
        </div>
      </div>
    </div>
  )
}

export default DashboardPage
