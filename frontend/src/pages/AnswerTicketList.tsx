import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getTickets, Ticket, TicketListResponse } from '../api/client'

const PAGE_SIZE = 20

export function AnswerTicketList() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [loading, setLoading] = useState(true)
  const [offset, setOffset] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadTickets = async () => {
    setLoading(true)
    setError(null)
    try {
      // Filter for in_progress and feedback statuses (tickets needing response)
      const resp: TicketListResponse = await getTickets({ status: 'in_progress', limit: PAGE_SIZE, offset })
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
    loadTickets()
  }, [offset])

  const goToPage = (page: number) => {
    setOffset(page * PAGE_SIZE)
  }

  const totalPages = Math.ceil(totalCount / PAGE_SIZE)
  const currentPage = Math.floor(offset / PAGE_SIZE)

  if (loading) return <div className="loading">読み込み中...</div>

  return (
    <div>
      <h1 style={{ marginBottom: '1rem' }}>回答者向けチケット一覧</h1>
      <div style={{ color: '#666', fontSize: '0.9rem', marginBottom: '1rem' }}>
        対応すべきチケット: {totalCount} 件
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

      {tickets.length === 0 ? (
        <div className="empty">対応すべきチケットはありません</div>
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
                <th>操作</th>
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
                  <td>
                    <Link to={`/tickets/${ticket.id}`}>
                      <button className="btn btn-primary" style={{ padding: '0.5rem 1rem' }}>
                        対応する
                      </button>
                    </Link>
                  </td>
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

              {[...Array(totalPages)].map((_, i) => (
                <button
                  key={i}
                  className={`btn ${i === currentPage ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => goToPage(i)}
                  style={{ padding: '0.4rem 0.8rem', minWidth: '2rem' }}
                >
                  {i + 1}
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
