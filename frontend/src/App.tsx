import { Routes, Route, Navigate } from 'react-router'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import WatchesPage from '@/pages/WatchesPage'
import StoresPage from '@/pages/StoresPage'

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <DashboardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/watches"
        element={
          <ProtectedRoute>
            <WatchesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stores"
        element={
          <ProtectedRoute>
            <StoresPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default App
