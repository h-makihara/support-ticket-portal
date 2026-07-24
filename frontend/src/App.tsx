import { useEffect, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { TicketList } from './pages/TicketList'
import { TicketDetail } from './pages/TicketDetail'
import { TicketCreate } from './pages/TicketCreate'
import { AnswerTicketList } from './pages/AnswerTicketList'
import { Login } from './pages/Login'
import { AuthUser, getSession, logout } from './api/client'

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
          <Route path="/" element={<TicketList />} />
          <Route path="/create" element={<TicketCreate />} />
          <Route path="/tickets/:id" element={<TicketDetail />} />
          <Route path="/answer" element={<AnswerTicketList />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
