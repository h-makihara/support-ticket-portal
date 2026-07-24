import { FormEvent, useState } from 'react'
import { login, AuthUser } from '../api/client'

export function Login({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      const session = await login(username, password)
      onLogin(session.user)
    } catch {
      setError('ユーザー名またはパスワードが正しくありません。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <form className="login-card" onSubmit={submit}>
        <div className="login-brand">社内問い合わせチケット管理</div>
        <h1>ログイン</h1>
        <p className="login-help">Redmine のアカウントでログインしてください。</p>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="form-group">
          <label htmlFor="username">ユーザー名</label>
          <input id="username" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required autoFocus />
        </div>
        <div className="form-group">
          <label htmlFor="password">パスワード</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        <button className="btn btn-primary login-button" disabled={submitting}>
          {submitting ? 'ログイン中…' : 'ログイン'}
        </button>
      </form>
    </main>
  )
}
