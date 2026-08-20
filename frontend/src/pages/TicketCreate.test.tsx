// @vitest-environment jsdom

import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { TicketCreate } from './TicketCreate'

const { createTicketMock, getTicketPriorityOptionsMock } = vi.hoisted(() => ({
  createTicketMock: vi.fn(),
  getTicketPriorityOptionsMock: vi.fn(),
}))

vi.mock('../api/client', () => ({
  createTicket: createTicketMock,
  getTicketPriorityOptions: getTicketPriorityOptionsMock,
}))

afterEach(cleanup)

beforeEach(() => {
  createTicketMock.mockReset().mockResolvedValue({ id: 1 })
  getTicketPriorityOptionsMock.mockReset().mockResolvedValue([
    { id: 1, label: '通常', is_default: true },
  ])
})

describe('TicketCreate', () => {
  it('submits the selected tracker', async () => {
    render(
      <MemoryRouter>
        <TicketCreate user={{ id: 1, username: 'sales', name: '営業', roles: ['sales'] }} />
      </MemoryRouter>,
    )

    await screen.findByRole('option', { name: '通常' })
    const tracker = screen.getByLabelText('トラッカー')
    expect(within(tracker).getAllByRole('option').map(option => option.textContent)).toEqual([
      '問い合わせ',
      '報告書',
      '客先同行',
    ])
    fireEvent.change(tracker, { target: { value: 'report' } })
    fireEvent.change(screen.getByPlaceholderText('件名を入力...'), { target: { value: '月次報告書' } })
    fireEvent.change(screen.getByPlaceholderText('問い合わせ内容を入力...'), { target: { value: '作成してください' } })
    fireEvent.click(screen.getByRole('button', { name: '作成する' }))

    await waitFor(() => expect(createTicketMock).toHaveBeenCalledWith(expect.objectContaining({
      tracker: 'report',
      subject: '月次報告書',
      description: '作成してください',
    })))
  })
})
