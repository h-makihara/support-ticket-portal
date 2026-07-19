import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getTickets, Ticket, TicketListResponse } from '../api/client'

const STATUS_OPTIONS = [
  { value: '', label: 'すべて' },
  { value: 'open', label: '未回答' },
  { value: 'in_progress', label: '回答中' },
  { value: 'feedback', label: '回答待ち' },
  { value: 'closed', label: 'クローズ' },
]

const PAGE_SIZE = 20

export function TicketList() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTickets = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp: TicketListResponse = await getTickets({ status: status || undefined, limit: PAGE_SIZE, offset })
      setTickets(resp.tickets)
      setTotalCount(resp.pagination.total_count)
      setHasMore(resp.pagination.has_more)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'チケットの取得に失敗しました'
      setError(msg)
      setTickets([])
      setTotalCount(0)
      setHasMore(false)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setOffset(0) // reset to first page when status changes
  }, [status])

  useEffect(() => {
    loadTickets()
  }, [status, offset])

  const goToPage = (page: number) => {
    setOffset(page * PAGE_SIZE)
  }

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE)

  // Generate page numbers to show
  const getPageNumbers = () => {
    const pages: number[] = []
    const maxVisible = 5
    let start = Math.max(0, currentPage - Math.floor(maxVisible / 2))
    const end = Math.min(totalPages, start + maxVisible)
    start = Math.max(0, end - maxVisible)
    for (let i = start; i < end; i++) {
      pages.push(i)
    }
    return pages
  }

  if (loading) return <div className="loading">読み込み中...</div>

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
        <h1>チケット一覧</h1>
        <Link to="/create">
          <button className="btn btn-primary">+ 新規作成</button>
        </Link>
      </div>

      {/* Error State */}
      {error && (
        <div style={{ padding: '0.8rem', backgroundColor: '#ffeaea', border: '1px solid #ffcccc', borderRadius: '4px', marginBottom: '1rem' }}>
          <strong>エラー:</strong> {error}
          <button className="btn btn-secondary" onClick={loadTickets} style={{ marginLeft: '0.5rem' }}>
            再試行
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', alignItems: 'center' }}>
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ddd' }}
        >
          {STATUS_OPTIONS.map(opt => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <span style={{ color: '#666', fontSize: '0.9rem' }}>
          合計 {totalCount} 件
        </span>
      </div>

      {tickets.length === 0 ? (
        <div className="empty">チケットがありません</div>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>件名</th>
                <th>ステータス</th>
                <th>優先度</th>
                <th>作成日</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map(ticket => (
                <tr key={ticket.id}>
                  <td>{ticket.id}</td>
                  <td>
                    <Link to={`/tickets/${ticket.id}`}>{ticket.subject}</Link>
                  </td>
                  <td>
                    <span className={`status-badge status-${ticket.status.toLowerCase().replace(/\s+/g, '_')}`}>
                      {ticket.status}
                    </span>
                  </td>
                  <td>{ticket.priority}</td>
                  <td>{ticket.created_on ? new Date(ticket.created_on).toLocaleDateString() : '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginTop: '1rem', flexWrap: 'wrap' }}>
              <button
                className="btn btn-secondary"
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 0}
                style={{ padding: '0.4rem 0.8rem' }}
              >
                ← 前へ
              </button>

              {getPageNumbers().map(page => (
                <button
                  key={page}
                  className={`btn ${page === currentPage ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => goToPage(page)}
                  style={{ padding: '0.4rem 0.8rem', minWidth: '2rem' }}
                >
                  {page + 1}
                </button>
              ))}

              <button
                className="btn btn-secondary"
                onClick={() => goToPage(currentPage + 1)}
                disabled={!hasMore}
                style={{ padding: '0.4rem 0.8rem' }}
              >
                次へ →
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
