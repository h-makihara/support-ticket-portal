import { useEffect, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { TicketList } from './pages/TicketList'
import { TicketDetail } from './pages/TicketDetail'
import { TicketCreate } from './pages/TicketCreate'
import { AnswerTicketList } from './pages/AnswerTicketList'
import { Login } from './pages/Login'
import { AuthUser, getSession, logout } from './api/client'
import { RequireCapability } from './components/RequireCapability'

function App() {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [checking, setChecking] = useState(true)

  useEffect(() => {
    getSession().then(session => setUser(session.user)).catch(() => setUser(null)).finally(() => setChecking(false))
    const expired = () => setUser(null)
    window.addEventListener('auth:unauthorized', expired)
    return () => window.removeEventListener('auth:unauthorized', expired)
  }, [])

  async function handleLogout() {
    try { await logout() } finally { setUser(null) }
  }

  if (checking) return <div className="loading auth-loading">ログイン状態を確認しています…</div>
  if (!user) return <Login onLogin={setUser} />

  return (
    <div className="app">
      <Navbar user={user} onLogout={handleLogout} />
      <main className="container">
        <Routes>
          <Route path="/" element={
            <RequireCapability user={user} capability="tickets:list">
              <TicketList />
            </RequireCapability>
          } />
          <Route path="/create" element={
            <RequireCapability user={user} capability="tickets:create" redirectTo="/">
              <TicketCreate user={user} />
            </RequireCapability>
          } />
          <Route path="/tickets/:id" element={<TicketDetail user={user} />} />
          <Route path="/answer" element={
            <RequireCapability user={user} capability="tickets:answer" redirectTo="/">
              <AnswerTicketList />
            </RequireCapability>
          } />
        </Routes>
      </main>
    </div>
  )
}

export default App
