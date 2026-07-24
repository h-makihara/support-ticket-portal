import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { createTicket } from '../api/client'

const PRIORITY_OPTIONS = [
  { id: 1, label: '低' },
  { id: 2, label: '通常' },
  { id: 3, label: '高' },
  { id: 4, label: '緊急' },
  { id: 5, label: '最優先' },
]

export function TicketCreate() {
  const navigate = useNavigate()
  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState(2)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: Event) => {
    e.preventDefault()
    if (!subject.trim() || !description.trim()) {
      setError('件名と本文は必須です')
      return
    }
    setLoading(true)
    setError(null) // Clear previous errors on new submit
    try {
      const ticket = await createTicket({ subject, description, priority })
      navigate(`/tickets/${ticket.id}`)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'チケットの作成に失敗しました'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <Link to="/" style={{ display: 'inline-block', marginBottom: '1rem', color: '#3498db', textDecoration: 'none' }}>
        ← 一覧に戻る
      </Link>

      <div className="card">
        <h1>新規チケット作成</h1>

        {/* Error State with retry option */}
        {error && (
          <div style={{ padding: '0.8rem', backgroundColor: '#ffeaea', border: '1px solid #ffcccc', borderRadius: '4px', marginTop: '1rem' }}>
            <strong>エラー:</strong> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ marginTop: '1rem' }}>
          <div className="form-group">
            <label>件名</label>
            <input
              type="text"
              value={subject}
              onChange={e => setSubject(e.target.value)}
              placeholder="件名を入力..."
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>本文</label>
            <textarea
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="問い合わせ内容を入力..."
              rows={8}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>優先度</label>
            <select
              value={priority}
              onChange={e => setPriority(parseInt(e.target.value))}
              disabled={loading}
            >
              {PRIORITY_OPTIONS.map(opt => (
                <option key={opt.id} value={opt.id}>{opt.label}</option>
              ))}
            </select>
          </div>

          <button className="btn btn-primary" type="submit" disabled={loading || !subject.trim() || !description.trim()}>
            {loading ? '作成中...' : '作成する'}
          </button>
        </form>
      </div>
    </div>
  )
}
