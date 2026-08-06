import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Ticket } from '../api/client'

const { getTicketsMock } = vi.hoisted(() => ({ getTicketsMock: vi.fn() }))
vi.mock('../api/client', () => ({ getTickets: getTicketsMock }))

import { fetchAllTickets, filterTicketsByStatus } from './TicketList'

const ticket = (id: number, status: string) => ({ id, status } as Ticket)

beforeEach(() => getTicketsMock.mockReset())

describe('ticket list cache', () => {
  it('fetches every page for the initial cache', async () => {
    getTicketsMock
      .mockResolvedValueOnce({ tickets: [ticket(1, '対応待ち')], pagination: { has_more: true } })
      .mockResolvedValueOnce({ tickets: [ticket(2, '対応中')], pagination: { has_more: false } })

    expect(await fetchAllTickets()).toEqual([ticket(1, '対応待ち'), ticket(2, '対応中')])
    expect(getTicketsMock).toHaveBeenCalledTimes(2)
    expect(getTicketsMock).toHaveBeenNthCalledWith(1, { limit: 1000, offset: 0 })
    expect(getTicketsMock).toHaveBeenNthCalledWith(2, { limit: 1000, offset: 1 })
  })

  it('filters the cached tickets without fetching again', () => {
    const tickets = [
      ticket(1, '対応待ち'),
      ticket(2, '対応中'),
      ticket(3, 'New'),
      ticket(4, 'クローズ'),
    ]

    expect(filterTicketsByStatus(tickets, 'open').map(item => item.id)).toEqual([1, 3])
    expect(filterTicketsByStatus(tickets, 'in_progress').map(item => item.id)).toEqual([2])
    expect(filterTicketsByStatus(tickets, 'closed').map(item => item.id)).toEqual([4])
    expect(filterTicketsByStatus(tickets, '').map(item => item.id)).toEqual([1, 2, 3, 4])
    expect(getTicketsMock).not.toHaveBeenCalled()
  })

  it('stops if an upstream page is empty even when has_more is inconsistent', async () => {
    getTicketsMock.mockResolvedValueOnce({
      tickets: [],
      pagination: { has_more: true },
    })

    expect(await fetchAllTickets()).toEqual([])
    expect(getTicketsMock).toHaveBeenCalledTimes(1)
  })

  it('does not hide tickets for an unknown local status key', () => {
    const tickets = [ticket(1, '独自ステータス')]

    expect(filterTicketsByStatus(tickets, 'unknown')).toBe(tickets)
  })
})
