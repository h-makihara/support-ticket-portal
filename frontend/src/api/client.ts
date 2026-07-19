const API_BASE = '/api'

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export interface Ticket {
  id: number
  subject: string
  description: string
  status: string
  priority: number
  created_on?: string
  updated_on?: string
  notes?: Array<{ body: string; author: string; created_on: string }>
}

export interface PaginationInfo {
  limit: number
  offset: number
  total_count: number
  has_more: boolean
}

export interface TicketListResponse {
  tickets: Ticket[]
  pagination: PaginationInfo
}

export interface GetTicketsOptions {
  status?: string
  limit?: number
  offset?: number
}

export async function getTickets(opts: GetTicketsOptions = {}): Promise<TicketListResponse> {
  const params = new URLSearchParams()
  if (opts.status) params.set('status', opts.status)
  if (opts.limit !== undefined) params.set('limit', String(opts.limit))
  if (opts.offset !== undefined) params.set('offset', String(opts.offset))

  const query = params.toString()
  const url = `/tickets${query ? `?${query}` : ''}`
  return request<TicketListResponse>(url)
}

export async function getTicket(id: number): Promise<Ticket> {
  return request<Ticket>(`/tickets/${id}`)
}

export async function createTicket(data: { subject: string; description: string; priority?: number }): Promise<Ticket> {
  return request<Ticket>('/tickets', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function addComment(ticketId: number, body: string): Promise<void> {
  await request(`/tickets/${ticketId}/comments`, {
    method: 'POST',
    body: JSON.stringify({ body }),
  })
}

export async function updateStatus(ticketId: number, statusId: number): Promise<void> {
  await request(`/tickets/${ticketId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status_id: statusId }),
  })
}

export interface TicketStatusOption {
  id: number
  label: string
}

export async function getTicketStatusOptions(): Promise<TicketStatusOption[]> {
  return request<TicketStatusOption[]>('/status/options')
}
