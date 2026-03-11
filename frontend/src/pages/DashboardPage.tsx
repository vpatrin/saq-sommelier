import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { Link, useNavigate } from 'react-router'

function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
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
            Nearby Stores
          </Link>
        </nav>

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
