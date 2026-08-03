import { describe, expect, it } from 'vitest'
import { capabilitiesFor, hasCapability } from './authz'

describe('role capabilities', () => {
  it('limits sales users to listing and creating tickets', () => {
    const capabilities = capabilitiesFor(['sales'])

    expect([...capabilities]).toEqual(['tickets:list', 'tickets:create'])
    expect(hasCapability({ roles: ['sales'] }, 'tickets:answer')).toBe(false)
  })

  it('allows support users to use every current ticket capability', () => {
    const user = { roles: ['support'] as const }

    expect(hasCapability(user, 'tickets:list')).toBe(true)
    expect(hasCapability(user, 'tickets:create')).toBe(true)
    expect(hasCapability(user, 'tickets:answer')).toBe(true)
  })

  it('combines capabilities when a user has multiple roles', () => {
    const capabilities = capabilitiesFor(['sales', 'support'])

    expect([...capabilities]).toEqual([
      'tickets:list',
      'tickets:create',
      'tickets:answer',
    ])
  })

  it('grants no capabilities when no portal role is assigned', () => {
    expect([...capabilitiesFor([])]).toEqual([])
  })

  it('safely ignores a role that this frontend does not know yet', () => {
    expect([...capabilitiesFor(['future-role'])]).toEqual([])
  })
})
