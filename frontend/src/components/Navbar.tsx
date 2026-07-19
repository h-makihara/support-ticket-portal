import { NavLink } from 'react-router-dom'

export function Navbar() {
  return (
    <nav className="navbar">
      <div style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>
        <NavLink to="/">社内問い合わせチケット管理</NavLink>
      </div>
      <div>
        <NavLink to="/">チケット一覧（営業）</NavLink>
        <NavLink to="/create">新規作成</NavLink>
        <NavLink to="/answer">回答者向け</NavLink>
      </div>
    </nav>
  )
}
