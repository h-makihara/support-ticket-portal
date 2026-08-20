import { test, expect } from './fixtures'
import {
  addComment,
  claimTicket,
  createTicket,
  expectStatus,
  openTicket,
  uniqueText,
  updateStatus,
} from './workflow'

test('営業とサポートが報告書と客先同行を別チケットで完了できる @full-regression', async ({
  salesPage,
  supportPage,
}) => {
  const tickets = [
    { tracker: '報告書' as const, ticket: await createTicket(salesPage, uniqueText('E2E-報告書-full-regression'), '報告書') },
    { tracker: '客先同行' as const, ticket: await createTicket(salesPage, uniqueText('E2E-客先同行-full-regression'), '客先同行') },
  ]
  expect(tickets[0].ticket.id).not.toBe(tickets[1].ticket.id)

  await salesPage.goto('/')
  for (const { tracker, ticket } of tickets) {
    const row = salesPage.getByRole('row').filter({ hasText: ticket.subject })
    await expect(row).toContainText(tracker)
  }

  for (const { tracker, ticket } of tickets) {
    await claimTicket(supportPage, ticket.id, ticket.subject)
    await addComment(supportPage, uniqueText(`${tracker}-サポートコメント`))

    const completionLabel = tracker === '報告書'
      ? '報告書を渡した'
      : '予定・担当者をアサインした'
    const unrelatedLabel = tracker === '報告書'
      ? '予定・担当者をアサインした'
      : '報告書を渡した'
    const completion = supportPage.getByLabel(completionLabel)
    await expect(completion).toBeVisible()
    await expect(supportPage.getByLabel(unrelatedLabel)).toHaveCount(0)
    await completion.check()
    await supportPage.getByRole('button', { name: '対応情報を更新' }).click()
    await expect(completion).toBeChecked()
    await expectStatus(supportPage, '対応済')

    await openTicket(salesPage, ticket.id, ticket.subject)
    await addComment(salesPage, uniqueText(`${tracker}-営業クローズ確認コメント`))
    await updateStatus(salesPage, 'クローズ待ち')

    await openTicket(supportPage, ticket.id, ticket.subject)
    await addComment(supportPage, uniqueText(`${tracker}-サポートクローズコメント`))
    await updateStatus(supportPage, 'クローズ')
  }
})
