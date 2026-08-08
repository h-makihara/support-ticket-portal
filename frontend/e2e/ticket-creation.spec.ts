import { test, expect } from './fixtures'
import { createTicket, expectStatus } from './workflow'

test('営業担当が新規チケットを作成できる @creation', async ({ salesPage }) => {
  const ticket = await createTicket(salesPage)

  await expect(salesPage.getByRole('heading', { name: ticket.subject })).toBeVisible()
  await expectStatus(salesPage, '対応待ち')
  await expect(salesPage.getByText('未割り当て', { exact: true })).toBeVisible()
})
