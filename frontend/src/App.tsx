import { Routes, Route } from 'react-router'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import LoginPage from '@/pages/LoginPage'
import DashboardPage from '@/pages/DashboardPage'
import WatchesPage from '@/pages/WatchesPage'
import SavedStoresPage from '@/pages/SavedStoresPage'
import NearbyStoresPage from '@/pages/StoresPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/invite/:code" element={<LoginPage />} />
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
            <SavedStoresPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/stores/nearby"
        element={
          <ProtectedRoute>
            <NearbyStoresPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<LoginPage />} />
    </Routes>
  )
}

export default App
