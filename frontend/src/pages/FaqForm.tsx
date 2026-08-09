import { FormEvent, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { createFaq, getFaq, updateFaq } from '../api/client'

export function FaqForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const [question, setQuestion] = useState('')
  const [answer, setAnswer] = useState('')
  const [version, setVersion] = useState<number | null>(null)
  const [loading, setLoading] = useState(editing)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    getFaq(id)
      .then(faq => {
        setQuestion(faq.question)
        setAnswer(faq.answer)
        setVersion(faq.version)
      })
      .catch(e => setError(e instanceof Error ? e.message : 'FAQの取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [id])

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (!question.trim() || !answer.trim()) return
    setSaving(true)
    setError(null)
    try {
      const faq = editing && id && version !== null
        ? await updateFaq(id, { question, answer, version })
        : await createFaq({ question, answer })
      navigate(`/faqs/${faq.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'FAQの保存に失敗しました')
      setSaving(false)
    }
  }

  if (loading) return <div className="loading">読み込み中...</div>

  return (
    <div>
      <Link to={editing && id ? `/faqs/${id}` : '/faqs'} className="back-link">← 戻る</Link>
      <div className="card faq-form-card">
        <p className="page-eyebrow">Knowledge base</p>
        <h1>{editing ? 'FAQを編集' : 'FAQを作成'}</h1>
        {error && <div className="error"><strong>エラー:</strong> {error}</div>}
        <form onSubmit={submit}>
          <div className="form-group">
            <label htmlFor="faq-question">質問</label>
            <input id="faq-question" maxLength={200} value={question} onChange={event => setQuestion(event.target.value)} disabled={saving} />
          </div>
          <div className="form-group">
            <label htmlFor="faq-answer">回答</label>
            <textarea id="faq-answer" rows={10} value={answer} onChange={event => setAnswer(event.target.value)} disabled={saving} />
          </div>
          <button className="btn btn-primary" disabled={saving || !question.trim() || !answer.trim()}>
            {saving ? '保存中…' : '保存する'}
          </button>
        </form>
      </div>
    </div>
  )
}
