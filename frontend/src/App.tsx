import { Routes, Route, Navigate } from 'react-router'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import AppShell from '@/components/AppShell'
import LoginPage from '@/pages/LoginPage'
import SearchPage from '@/pages/SearchPage'
import WatchesPage from '@/pages/WatchesPage'
import SavedStoresPage from '@/pages/SavedStoresPage'
import NearbyStoresPage from '@/pages/StoresPage'

function AuthedLayout() {
  return (
    <ProtectedRoute>
      <AppShell />
    </ProtectedRoute>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/invite/:code" element={<LoginPage />} />
      <Route path="/dashboard" element={<Navigate to="/search" replace />} />
      <Route element={<AuthedLayout />}>
        <Route path="/search" element={<SearchPage />} />
        <Route path="/watches" element={<WatchesPage />} />
        <Route path="/stores" element={<SavedStoresPage />} />
        <Route path="/stores/nearby" element={<NearbyStoresPage />} />
      </Route>
      <Route path="*" element={<LoginPage />} />
    </Routes>
  )
}

export default App
