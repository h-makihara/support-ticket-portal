const API_BASE = '/api'

async function request<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    credentials: 'include',
    ...options,
  })
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event('auth:unauthorized'))
    const body = await response.json().catch(() => null)
    const detail = body?.detail
    throw new Error(
      typeof detail === 'string' && detail
        ? detail
        : `API error: ${response.status} ${response.statusText}`,
    )
  }
  return response.json()
}

export interface AuthUser {
  id: number
  username: string
  name: string
  roles: string[]
}

export interface AuthSession {
  authenticated: true
  user: AuthUser
}

export function getSession(): Promise<AuthSession> {
  return request<AuthSession>('/auth/session')
}

export function login(username: string, password: string): Promise<AuthSession> {
  return request<AuthSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
}

export function logout(): Promise<{ detail: string }> {
  return request('/auth/logout', { method: 'POST' })
}

export interface Ticket {
  id: number
  subject: string
  description: string
  status: string
  priority: number
  assignee: {
    id: number
    name: string
  } | null
  created_on?: string
  updated_on?: string
  notes?: Array<{ body: string; author: string; created_on: string }>
  audit_log?: AuditEntry[]
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
  responderView?: boolean
  limit?: number
  offset?: number
}

export async function getTickets(opts: GetTicketsOptions = {}): Promise<TicketListResponse> {
  const params = new URLSearchParams()
  if (opts.status) params.set('status', opts.status)
  if (opts.responderView) params.set('view', 'responder')
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

export async function answerTicket(ticketId: number, body: string): Promise<void> {
  await request(`/tickets/${ticketId}/answer`, {
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

export async function claimTicket(ticketId: number): Promise<void> {
  await request(`/tickets/${ticketId}/assignee`, {
    method: 'PATCH',
  })
}

export interface TicketStatusOption {
  id: number
  label: string
}

export async function getTicketStatusOptions(): Promise<TicketStatusOption[]> {
  return request<TicketStatusOption[]>('/status/options')
}

// ── Audit Log Types ────────────────────────────────────────────────

export interface AuditChange {
  field: string
  display_field: string
  old_value?: string | null
  new_value?: string | null
}

export interface AuditEntry {
  type: 'comment' | 'change' | 'both'
  author: string
  created_on: string
  comment?: string
  changes: AuditChange[]
}
