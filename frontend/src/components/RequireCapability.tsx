import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import type { AuthUser } from '../api/client'
import { hasCapability } from '../authz'
import type { Capability } from '../authz'

interface RequireCapabilityProps {
  user: AuthUser
  capability: Capability
  children: ReactNode
  redirectTo?: string
}

export function RequireCapability({
  user,
  capability,
  children,
  redirectTo,
}: RequireCapabilityProps) {
  if (hasCapability(user, capability)) return <>{children}</>
  if (redirectTo) return <Navigate to={redirectTo} replace />
  return <div className="empty">この画面を表示する権限がありません</div>
}
