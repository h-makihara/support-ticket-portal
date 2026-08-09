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
  { to: '/faqs', label: 'FAQ', capability: 'faqs:read' },
]

export function Navbar({ user, onLogout }: { user: AuthUser; onLogout: () => void }) {
  return (
    <nav className="navbar" aria-label="メインナビゲーション">
      <div className="navbar-inner">
        <NavLink className="brand" to="/" aria-label="Support Portal ホーム">
          <span className="brand-mark" aria-hidden="true">S</span>
          <span>Support Portal</span>
        </NavLink>
        <div className="nav-links">
        {NAV_ITEMS.filter(item => hasCapability(user, item.capability)).map(item => (
          <NavLink key={item.to} to={item.to} end={item.to === '/'}>{item.label}</NavLink>
        ))}
        </div>
        <div className="nav-account">
        <span className="nav-user">{user.name}</span>
        <button className="nav-logout" onClick={onLogout}>ログアウト</button>
        </div>
      </div>
    </nav>
  )
}
