// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { AuthUser } from '../api/client'
import { Navbar } from './Navbar'

afterEach(cleanup)

function renderNavbar(roles: AuthUser['roles']) {
  const user: AuthUser = {
    id: 1,
    username: 'user',
    name: 'Test User',
    roles,
  }
  render(
    <MemoryRouter>
      <Navbar user={user} onLogout={vi.fn()} />
    </MemoryRouter>,
  )
}

describe('Navbar authorization', () => {
  it('shows sales features but hides the responder link from sales users', () => {
    renderNavbar(['sales'])

    expect(screen.getByRole('link', { name: 'チケット一覧' })).toBeVisible()
    expect(screen.getByRole('link', { name: '新規作成' })).toBeVisible()
    expect(screen.queryByRole('link', { name: '回答者向け' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'FAQ' })).toBeVisible()
  })

  it('shows all current features to support users', () => {
    renderNavbar(['support'])

    expect(screen.getByRole('link', { name: 'チケット一覧' })).toBeVisible()
    expect(screen.getByRole('link', { name: '新規作成' })).toBeVisible()
    expect(screen.getByRole('link', { name: '回答者向け' })).toBeVisible()
    expect(screen.getByRole('link', { name: 'FAQ' })).toBeVisible()
  })

  it('shows only FAQ navigation to administrators', () => {
    renderNavbar(['admin'])

    expect(screen.getByRole('link', { name: 'FAQ' })).toBeVisible()
    expect(screen.queryByRole('link', { name: 'チケット一覧' })).not.toBeInTheDocument()
  })
})
