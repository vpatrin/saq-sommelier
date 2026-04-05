import { Navigate } from 'react-router'
import { useAuth } from '@/contexts/AuthContext'
import type { ReactNode } from 'react'

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token } = useAuth()

  if (!token) {
    return <Navigate to="/" replace />
  }

  if (!localStorage.getItem('onboarded')) {
    return <Navigate to="/onboarding" replace />
  }

  return children
}
