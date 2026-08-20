import { test, expect } from './fixtures'
import { createTicket, uniqueText } from './workflow'

for (const tracker of ['報告書', '客先同行'] as const) {
  test(`営業担当が「${tracker}」トラッカーのチケットを作成できる @requirements`, async ({ salesPage }) => {
    const ticket = await createTicket(salesPage, uniqueText(`E2E-${tracker}`), tracker)

    await expect(salesPage.getByText(`トラッカー: ${tracker}`, { exact: true })).toBeVisible()
    await salesPage.goto('/')
    const row = salesPage.getByRole('row').filter({ hasText: ticket.subject })
    await expect(row).toContainText(tracker)
  })
}
