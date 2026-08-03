export const KNOWN_USER_ROLES = ['sales', 'support'] as const
export type KnownUserRole = typeof KNOWN_USER_ROLES[number]

export const CAPABILITIES = [
  'tickets:list',
  'tickets:create',
  'tickets:answer',
] as const
export type Capability = typeof CAPABILITIES[number]

const ROLE_CAPABILITIES: Record<KnownUserRole, ReadonlySet<Capability>> = {
  sales: new Set(['tickets:list', 'tickets:create']),
  support: new Set(CAPABILITIES),
}

export interface RoleBearingUser {
  roles: readonly string[]
}

export function capabilitiesFor(roles: readonly string[]): ReadonlySet<Capability> {
  return new Set(roles.flatMap(role => [
    ...(ROLE_CAPABILITIES[role as KnownUserRole] ?? []),
  ]))
}

export function hasCapability(
  user: RoleBearingUser,
  capability: Capability,
): boolean {
  return capabilitiesFor(user.roles).has(capability)
}
