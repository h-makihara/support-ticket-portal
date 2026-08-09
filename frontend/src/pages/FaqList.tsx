import { FormEvent, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Faq, getFaqs, AuthUser } from '../api/client'
import { hasCapability } from '../authz'

const PAGE_SIZE = 20

export function FaqList({ user }: { user: AuthUser }) {
  const [faqs, setFaqs] = useState<Faq[]>([])
  const [query, setQuery] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [totalCount, setTotalCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    getFaqs(activeQuery, PAGE_SIZE, offset)
      .then(result => {
        setFaqs(result.faqs)
        setTotalCount(result.pagination.total_count)
        setHasMore(result.pagination.has_more)
      })
      .catch(e => setError(e instanceof Error ? e.message : 'FAQの取得に失敗しました'))
      .finally(() => setLoading(false))
  }, [activeQuery, offset])

  function search(event: FormEvent) {
    event.preventDefault()
    setOffset(0)
    setActiveQuery(query.trim())
  }

  return (
    <div>
      <div className="page-heading">
        <div>
          <p className="page-eyebrow">Knowledge base</p>
          <h1>FAQ</h1>
        </div>
        {hasCapability(user, 'faqs:write') && (
          <Link to="/faqs/new" className="btn btn-primary faq-create-link">+ FAQを作成</Link>
        )}
      </div>

      <form className="faq-search" role="search" onSubmit={search}>
        <label htmlFor="faq-search-input">FAQを検索</label>
        <div className="faq-search-row">
          <input
            id="faq-search-input"
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="質問や回答のキーワードを入力"
          />
          <button className="btn btn-primary" type="submit">検索</button>
        </div>
      </form>

      {error && <div className="error"><strong>エラー:</strong> {error}</div>}
      {loading ? (
        <div className="loading">読み込み中...</div>
      ) : faqs.length === 0 ? (
        <div className="empty">該当するFAQがありません</div>
      ) : (
        <div className="faq-list" aria-label="FAQ一覧">
          {faqs.map(faq => (
            <article className="faq-list-item" key={faq.id}>
              <p className="faq-prefix">Q</p>
              <div>
                <h2><Link to={`/faqs/${faq.id}`}>{faq.question}</Link></h2>
                <p>{faq.answer}</p>
                <span>更新日 {faq.updated_on ? new Date(faq.updated_on).toLocaleDateString() : '-'}</span>
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && totalCount > PAGE_SIZE && (
        <div className="pagination">
          <button className="btn btn-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>← 前へ</button>
          <span className="ticket-count">{offset + 1}–{Math.min(offset + faqs.length, totalCount)} / {totalCount}件</span>
          <button className="btn btn-secondary" disabled={!hasMore} onClick={() => setOffset(offset + PAGE_SIZE)}>次へ →</button>
        </div>
      )}
    </div>
  )
}
