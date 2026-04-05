import { Routes, Route, Navigate } from 'react-router'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import AppShell from '@/components/AppShell'
import LandingPage from '@/pages/LandingPage'
import LoginPage from '@/pages/LoginPage'
import AuthCallbackPage from '@/pages/AuthCallbackPage'
import ChatPage from '@/pages/ChatPage'
import ChatsPage from '@/pages/ChatsPage'
import SearchPage from '@/pages/SearchPage'
import WatchesPage from '@/pages/WatchesPage'
import SavedStoresPage from '@/pages/SavedStoresPage'
import NearbyStoresPage from '@/pages/StoresPage'
import TastingsPage from '@/pages/TastingsPage'
import AdminPage from '@/pages/AdminPage'

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
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route element={<AuthedLayout />}>
        <Route path="/dashboard" element={<Navigate to="/chat" replace />} />
        <Route path="/chats" element={<ChatsPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/chat/:sessionId" element={<ChatPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/watches" element={<WatchesPage />} />
        <Route path="/stores" element={<SavedStoresPage />} />
        <Route path="/stores/nearby" element={<NearbyStoresPage />} />
        <Route path="/tastings" element={<TastingsPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
      <Route path="*" element={<LandingPage />} />
    </Routes>
  )
}

export default App
