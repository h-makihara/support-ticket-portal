import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { AuthUser, createTicket } from '../api/client'

const PRIORITY_OPTIONS = [
  { id: 1, label: '低' },
  { id: 2, label: '通常' },
  { id: 3, label: '高' },
  { id: 4, label: '緊急' },
  { id: 5, label: '最優先' },
]

export function TicketCreate({ user }: { user: AuthUser }) {
  const navigate = useNavigate()
  const [subject, setSubject] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState(2)
  const [customerId, setCustomerId] = useState('')
  const [reportRequired, setReportRequired] = useState(false)
  const [reportDelivered, setReportDelivered] = useState(false)
  const [customerVisitRequired, setCustomerVisitRequired] = useState(false)
  const [scheduleAssigned, setScheduleAssigned] = useState(false)
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
      const ticket = await createTicket({
        subject, description, priority,
        customer_id: customerId,
        report_required: reportRequired,
        report_delivered: reportDelivered,
        customer_visit_required: customerVisitRequired,
        schedule_assigned: scheduleAssigned,
      })
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

          <div className="form-group">
            <label htmlFor="customer-id">顧客ID</label>
            <input id="customer-id" type="text" value={customerId} onChange={e => setCustomerId(e.target.value)} disabled={loading} />
          </div>

          <div className="custom-field-checks">
            <label><input type="checkbox" checked={reportRequired} onChange={e => setReportRequired(e.target.checked)} disabled={loading} /> 報告書が必要</label>
            <label><input type="checkbox" checked={customerVisitRequired} onChange={e => setCustomerVisitRequired(e.target.checked)} disabled={loading} /> 客先同行が必要</label>
            {user.roles.includes('support') && <>
              <label><input type="checkbox" checked={reportDelivered} onChange={e => setReportDelivered(e.target.checked)} disabled={loading} /> 報告書を渡した</label>
              <label><input type="checkbox" checked={scheduleAssigned} onChange={e => setScheduleAssigned(e.target.checked)} disabled={loading} /> 予定・担当者をアサインした</label>
            </>}
          </div>

          <button className="btn btn-primary" type="submit" disabled={loading || !subject.trim() || !description.trim()}>
            {loading ? '作成中...' : '作成する'}
          </button>
        </form>
      </div>
    </div>
  )
}
