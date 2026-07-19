import { Routes, Route } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { TicketList } from './pages/TicketList'
import { TicketDetail } from './pages/TicketDetail'
import { TicketCreate } from './pages/TicketCreate'
import { AnswerTicketList } from './pages/AnswerTicketList'

function App() {
  return (
    <div className="app">
      <Navbar />
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
