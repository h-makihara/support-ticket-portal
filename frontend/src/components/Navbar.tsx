import { NavLink } from 'react-router-dom'
import { AuthUser } from '../api/client'
import { hasCapability } from '../authz'
import type { Capability } from '../authz'

export const NAV_ITEMS: ReadonlyArray<{
  to: string
  label: string
  capability: Capability
}> = [
  { to: '/', label: 'チケット一覧', capability: 'tickets:list' },
  { to: '/create', label: '新規作成', capability: 'tickets:create' },
  { to: '/answer', label: '回答者向け', capability: 'tickets:answer' },
]

export function Navbar({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  return (
    <nav className="navbar">
      <div style={{ fontWeight: 'bold', fontSize: '1.25rem' }}>
        <NavLink to="/">社内問い合わせチケット管理</NavLink>
      </div>
      <div>
        {NAV_ITEMS.filter(item => hasCapability(user, item.capability)).map(item => (
          <NavLink key={item.to} to={item.to}>{item.label}</NavLink>
        ))}
        <span className="nav-user">{user.name}</span>
        <button className="nav-logout" onClick={onLogout}>ログアウト</button>
      </div>
    </nav>
  )
}
