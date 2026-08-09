import { describe, expect, it } from 'vitest'
import { capabilitiesFor, hasCapability } from './authz'

describe('role capabilities', () => {
  it('allows sales users to read FAQs but not edit them', () => {
    const capabilities = capabilitiesFor(['sales'])

    expect([...capabilities]).toEqual(['tickets:list', 'tickets:create', 'faqs:read'])
    expect(hasCapability({ roles: ['sales'] }, 'tickets:answer')).toBe(false)
    expect(hasCapability({ roles: ['sales'] }, 'faqs:write')).toBe(false)
  })

  it('allows support users to use every current ticket capability', () => {
    const user = { roles: ['support'] as const }

    expect(hasCapability(user, 'tickets:list')).toBe(true)
    expect(hasCapability(user, 'tickets:create')).toBe(true)
    expect(hasCapability(user, 'tickets:answer')).toBe(true)
    expect(hasCapability(user, 'faqs:read')).toBe(true)
    expect(hasCapability(user, 'faqs:write')).toBe(true)
  })

  it('combines capabilities when a user has multiple roles', () => {
    const capabilities = capabilitiesFor(['sales', 'support'])

    expect([...capabilities]).toEqual([
      'tickets:list',
      'tickets:create',
      'faqs:read',
      'tickets:answer',
      'faqs:write',
    ])
  })

  it('limits administrators to FAQ management in the portal', () => {
    expect([...capabilitiesFor(['admin'])]).toEqual(['faqs:read', 'faqs:write'])
  })

  it('grants no capabilities when no portal role is assigned', () => {
    expect([...capabilitiesFor([])]).toEqual([])
  })

  it('safely ignores a role that this frontend does not know yet', () => {
    expect([...capabilitiesFor(['future-role'])]).toEqual([])
  })
})
