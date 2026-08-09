import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AuthUser, deleteFaq, Faq, getFaq } from '../api/client'
import { hasCapability } from '../authz'

export function FaqDetail({ user }: { user: AuthUser }) {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const [faq, setFaq] = useState<Faq | null>(null)
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getFaq(id)
      .then(setFaq)
      .catch(e => setError(e instanceof Error ? e.message : 'FAQの取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [id])

  async function remove() {
    setDeleting(true)
    setError(null)
    try {
      await deleteFaq(id)
      navigate('/faqs')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'FAQの削除に失敗しました')
      setConfirming(false)
      setDeleting(false)
    }
  }

  if (loading) return <div className="loading">読み込み中...</div>
  if (!faq) return <div className="error">{error || 'FAQが見つかりません'}</div>

  return (
    <div>
      <Link to="/faqs" className="back-link">← FAQ一覧に戻る</Link>
      {error && <div className="error"><strong>エラー:</strong> {error}</div>}
      <article className="faq-detail card">
        <p className="faq-prefix">Q</p>
        <h1>{faq.question}</h1>
        <div className="faq-answer">
          <p className="faq-prefix">A</p>
          <p>{faq.answer}</p>
        </div>
        <footer>
          <span>更新日 {faq.updated_on ? new Date(faq.updated_on).toLocaleString() : '-'}</span>
          {faq.author && <span>更新者 {faq.author}</span>}
        </footer>
      </article>
      {hasCapability(user, 'faqs:write') && (
        <div className="faq-actions">
          <Link className="btn btn-primary" to={`/faqs/${faq.id}/edit`}>編集</Link>
          <button className="btn btn-danger" onClick={() => setConfirming(true)}>削除</button>
        </div>
      )}
      {confirming && (
        <div className="modal-backdrop">
          <div className="confirm-dialog" role="dialog" aria-modal="true" aria-label="FAQを削除しますか？">
            <h2>FAQを削除しますか？</h2>
            <p>「{faq.question}」を削除します。この操作は取り消せません。</p>
            <div className="confirm-dialog-actions">
              <button className="btn btn-secondary" disabled={deleting} onClick={() => setConfirming(false)}>キャンセル</button>
              <button className="btn btn-danger" disabled={deleting} onClick={remove}>{deleting ? '削除中…' : '削除する'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
