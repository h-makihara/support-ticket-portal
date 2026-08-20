// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { Ticket } from '../api/client'
import { TicketDetail } from './TicketDetail'

const { getTicketMock, getTicketPriorityOptionsMock, getTicketStatusOptionsMock } = vi.hoisted(() => ({
  getTicketMock: vi.fn(),
  getTicketPriorityOptionsMock: vi.fn(),
  getTicketStatusOptionsMock: vi.fn(),
}))

vi.mock('../api/client', () => ({
  getTicket: getTicketMock,
  getTicketPriorityOptions: getTicketPriorityOptionsMock,
  getTicketStatusOptions: getTicketStatusOptionsMock,
}))

afterEach(cleanup)

const supportUser = { id: 1, username: 'support', name: 'サポート', roles: ['support'] }

function ticket(tracker: Ticket['tracker'], trackerName: string): Ticket {
  return {
    id: 1,
    subject: 'チケット',
    description: '本文',
    status: '新規',
    priority: 1,
    priority_name: '通常',
    tracker,
    tracker_name: trackerName,
    assignee: null,
    customer_id: '',
  }
}

function renderTicketDetail() {
  render(
    <MemoryRouter initialEntries={['/tickets/1']}>
      <Routes>
        <Route path="/tickets/:id" element={<TicketDetail user={supportUser} />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  getTicketMock.mockReset()
  getTicketStatusOptionsMock.mockReset().mockResolvedValue([{ id: 1, label: '新規' }])
  getTicketPriorityOptionsMock.mockReset().mockResolvedValue([{ id: 1, label: '通常', is_default: true }])
})

describe('TicketDetail tracker controls', () => {
  it('shows only the report completion control for report tickets', async () => {
    getTicketMock.mockResolvedValue(ticket('report', '報告書'))
    renderTicketDetail()

    expect(await screen.findByText('トラッカー: 報告書')).toBeVisible()
    expect(screen.getByLabelText('報告書を渡した')).toBeVisible()
    expect(screen.queryByLabelText('予定・担当者をアサインした')).not.toBeInTheDocument()
  })

  it('shows only the schedule completion control for customer-visit tickets', async () => {
    getTicketMock.mockResolvedValue(ticket('customer_visit', '客先同行'))
    renderTicketDetail()

    expect(await screen.findByText('トラッカー: 客先同行')).toBeVisible()
    expect(screen.queryByLabelText('報告書を渡した')).not.toBeInTheDocument()
    expect(screen.getByLabelText('予定・担当者をアサインした')).toBeVisible()
  })

  it('shows neither completion control for inquiry tickets', async () => {
    getTicketMock.mockResolvedValue(ticket('inquiry', '問い合わせ'))
    renderTicketDetail()

    expect(await screen.findByText('トラッカー: 問い合わせ')).toBeVisible()
    expect(screen.queryByLabelText('報告書を渡した')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('予定・担当者をアサインした')).not.toBeInTheDocument()
  })
})
