// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it } from 'vitest'
import type { AuthUser } from '../api/client'
import { RequireCapability } from './RequireCapability'

afterEach(cleanup)

const salesUser: AuthUser = {
  id: 1,
  username: 'sales',
  name: 'Sales User',
  roles: ['sales'],
}

describe('RequireCapability', () => {
  it('renders a protected screen when the capability is granted', () => {
    render(
      <MemoryRouter>
        <RequireCapability user={salesUser} capability="tickets:create">
          <div>新規作成画面</div>
        </RequireCapability>
      </MemoryRouter>,
    )

    expect(screen.getByText('新規作成画面')).toBeVisible()
  })

  it('redirects when the capability is missing', () => {
    render(
      <MemoryRouter initialEntries={['/answer']}>
        <Routes>
          <Route path="/" element={<div>チケット一覧画面</div>} />
          <Route path="/answer" element={
            <RequireCapability
              user={salesUser}
              capability="tickets:answer"
              redirectTo="/"
            >
              <div>回答者向け画面</div>
            </RequireCapability>
          } />
        </Routes>
      </MemoryRouter>,
    )

    expect(screen.getByText('チケット一覧画面')).toBeVisible()
    expect(screen.queryByText('回答者向け画面')).not.toBeInTheDocument()
  })
})
