import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AuthUser, getTickets, Ticket } from '../api/client'
import { priorityBadgeClass, priorityLabel } from '../priority'

const STATUS_OPTIONS = [
  { value: '', label: 'すべて', names: [] },
  { value: 'open', label: '新規', names: ['新規', 'New'] },
  { value: 'in_progress', label: '対応中', names: ['対応中', 'In Progress'] },
  { value: 'answered', label: '回答済', names: ['回答済', 'Resolved'] },
  { value: 'additional_question', label: '追加質問', names: ['追加質問', 'Feedback', 'Reopened'] },
  { value: 'pending_close', label: 'クローズ待ち', names: ['クローズ待ち', 'Rejected'] },
  { value: 'closed', label: 'クローズ', names: ['クローズ', 'Closed'] },
]

const PAGE_SIZE = 20
const FETCH_PAGE_SIZE = 1000

export async function fetchAllTickets(): Promise<Ticket[]> {
  const allTickets: Ticket[] = []
  let offset = 0
  let hasMore = true

  while (hasMore) {
    const response = await getTickets({ limit: FETCH_PAGE_SIZE, offset })
    allTickets.push(...response.tickets)
    hasMore = response.pagination.has_more
    offset += response.tickets.length
    if (response.tickets.length === 0) break
  }
  return allTickets
}

export function filterTicketsByStatus(tickets: Ticket[], status: string): Ticket[] {
  const option = STATUS_OPTIONS.find(candidate => candidate.value === status)
  if (!option || option.names.length === 0) return tickets
  return tickets.filter(ticket => option.names.includes(ticket.status))
}

export function TicketList({ user }: { user: AuthUser }) {
  const [allTickets, setAllTickets] = useState<Ticket[]>([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const loadTickets = async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true)
    setError(null)
    try {
      setAllTickets(await fetchAllTickets())
      setOffset(0)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'チケットの取得に失敗しました')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadTickets()
  }, [])

  useEffect(() => {
    setOffset(0)
  }, [status])

  const filteredTickets = useMemo(
    () => filterTicketsByStatus(allTickets, status),
    [allTickets, status],
  )
  const tickets = filteredTickets.slice(offset, offset + PAGE_SIZE)
  const totalCount = filteredTickets.length
  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE)

  const getPageNumbers = () => {
    const pages: number[] = []
    const maxVisible = 5
    let start = Math.max(0, currentPage - Math.floor(maxVisible / 2))
    const end = Math.min(totalPages, start + maxVisible)
    start = Math.max(0, end - maxVisible)
    for (let i = start; i < end; i++) pages.push(i)
    return pages
  }

  if (loading) return <div className="loading">読み込み中...</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>チケット一覧</h1>
        <Link to="/create"><button className="btn btn-primary">+ 新規作成</button></Link>
      </div>

      {error && (
        <div className="error">
          <strong>エラー:</strong> {error}
          <button className="btn btn-secondary" onClick={() => loadTickets()} style={{ marginLeft: '0.5rem' }}>再試行</button>
        </div>
      )}

      <div className="ticket-list-toolbar">
        <select value={status} onChange={e => setStatus(e.target.value)} aria-label="ステータスで絞り込み">
          {STATUS_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
        </select>
        <span className="ticket-count">合計 {totalCount} 件</span>
        {user.roles.includes('support') && (
          <button className="btn btn-secondary refresh-button" onClick={() => loadTickets(true)} disabled={refreshing}>
            {refreshing ? '更新中…' : '↻ 更新'}
          </button>
        )}
      </div>

      {tickets.length === 0 ? (
        <div className="empty">チケットがありません</div>
      ) : (
        <>
          <table className="table">
            <thead><tr><th>ID</th><th>件名</th><th>ステータス</th><th>優先度</th><th>作成日</th></tr></thead>
            <tbody>
              {tickets.map(ticket => (
                <tr key={ticket.id}>
                  <td>{ticket.id}</td>
                  <td><Link to={`/tickets/${ticket.id}`}>{ticket.subject}</Link></td>
                  <td><span className={`status-badge status-${ticket.status.toLowerCase().replace(/\s+/g, '_')}`}>{ticket.status}</span></td>
                  <td><span className={priorityBadgeClass(ticket)}>{priorityLabel(ticket)}</span></td>
                  <td>{ticket.created_on ? new Date(ticket.created_on).toLocaleDateString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {totalPages > 1 && (
            <div className="pagination">
              <button className="btn btn-secondary" onClick={() => setOffset((currentPage - 1) * PAGE_SIZE)} disabled={currentPage === 0}>← 前へ</button>
              {getPageNumbers().map(page => (
                <button key={page} className={`btn ${page === currentPage ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setOffset(page * PAGE_SIZE)}>{page + 1}</button>
              ))}
              <button className="btn btn-secondary" onClick={() => setOffset((currentPage + 1) * PAGE_SIZE)} disabled={currentPage >= totalPages - 1}>次へ →</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
