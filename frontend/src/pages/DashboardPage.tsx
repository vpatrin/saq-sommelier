import { useAuth } from '@/contexts/AuthContext'
import { Button } from '@/components/ui/button'
import { useNavigate } from 'react-router'

function DashboardPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col items-center justify-center gap-6">
      <h1 className="text-4xl font-mono font-bold">
        Welcome, {user?.first_name}
      </h1>
      <Button variant="outline" onClick={handleLogout}>
        Logout
      </Button>
    </div>
  )
}

export default DashboardPage
