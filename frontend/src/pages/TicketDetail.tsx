import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTicket, addComment, updateStatus, getTicketStatusOptions, Ticket, TicketStatusOption, AuditEntry } from '../api/client'
import { AuditLog } from '../components/AuditLog'

export function TicketDetail() {
  const { id } = useParams<{ id: string }>()
  const [ticket, setTicket] = useState<Ticket | null>(null)
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([])
  const [comment, setComment] = useState('')
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusOptions, setStatusOptions] = useState<TicketStatusOption[]>([])

  const loadTicketData = async () => {
    if (!id) return
    setLoading(true)
    setError(null)
    try {
      const [t, opts] = await Promise.all([
        getTicket(parseInt(id)),
        getTicketStatusOptions(),
      ])
      setTicket(t)
      setAuditLog((t as any).audit_log || [])
      setStatusOptions(opts)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'チケットの取得に失敗しました'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadTicketData()
  }, [id])

  const handleComment = async () => {
    if (!id || !comment.trim()) return
    try {
      await addComment(parseInt(id), comment)
      setComment('')
      setError(null) // Clear any previous error on success.
      await loadTicketData()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'コメントの追加に失敗しました'
      setError(msg)
    }
  }

  const handleStatus = async (statusId: number) => {
    if (!id) return
    try {
      await updateStatus(parseInt(id), statusId)
      setError(null) // Clear any previous error on success.
      await loadTicketData()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'ステータスの変更に失敗しました'
      setError(msg)
    }
  }

  if (loading) return <div className="loading">読み込み中...</div>

  // Loading error state with retry button.
  if (!ticket && error) {
    return (
      <div>
        <Link to="/" style={{ display: 'inline-block', marginBottom: '1rem' }}>
          ← 一覧に戻る
        </Link>
        <div style={{ padding: '1rem', backgroundColor: '#ffeaea', border: '1px solid #ffcccc', borderRadius: '4px' }}>
          <strong>エラー:</strong> {error}
          <button className="btn btn-secondary" onClick={loadTicketData} style={{ marginLeft: '0.5rem' }}>
            再試行
          </button>
        </div>
      </div>
    )
  }

  if (!ticket) return <div className="empty">チケットが見つかりません</div>

  return (
    <div>
      <Link to="/" style={{ display: 'inline-block', marginBottom: '1rem' }}>
        ← 一覧に戻る
      </Link>

      {/* Error Banner */}
      {error && (
        <div style={{ padding: '0.8rem', backgroundColor: '#ffeaea', border: '1px solid #ffcccc', borderRadius: '4px', marginBottom: '1rem' }}>
          <strong>エラー:</strong> {error}
          <button className="btn btn-secondary" onClick={loadTicketData} style={{ marginLeft: '0.5rem' }}>
            再試行
          </button>
        </div>
      )}

      {/* Ticket info card */}
      <div className="card">
        <h1>{ticket.subject}</h1>
        <div style={{ marginTop: '1rem', color: '#666' }}>
          <strong>ID:</strong> {ticket.id} | <strong>ステータス:</strong> {ticket.status} | <strong>優先度:</strong> {ticket.priority}
        </div>
        <div style={{ marginTop: '1rem', whiteSpace: 'pre-wrap' }}>{ticket.description}</div>
      </div>

      {/* Full audit log with comments + field changes */}
      <AuditLog entries={auditLog} />

      {/* Comment form */}
      <div className="card" style={{ marginTop: '1rem' }}>
        <h3>コメント追加</h3>
        {error && <div style={{ color: '#e74c3c', marginBottom: '0.5rem' }}>{error}</div>}
        <div className="form-group">
          <textarea
            value={comment}
            onChange={e => setComment(e.target.value)}
            placeholder="コメントを入力..."
          />
        </div>
        <button className="btn btn-primary" onClick={handleComment} disabled={!comment.trim()}>
          送信
        </button>
      </div>

      {/* Status change form */}
      <div className="card" style={{ marginTop: '1rem' }}>
        <h3>ステータス変更</h3>
        <select
          value={status}
          onChange={e => setStatus(e.target.value)}
          style={{ padding: '0.5rem', borderRadius: '4px', border: '1px solid #ddd', marginRight: '0.5rem' }}
        >
          {statusOptions.map(opt => (
            <option key={opt.id} value={opt.id}>{opt.label}</option>
          ))}
        </select>
        <button className="btn btn-success" onClick={() => handleStatus(parseInt(status))}>
          更新
        </button>
      </div>
    </div>
  )
}
