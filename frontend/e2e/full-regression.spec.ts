import { test } from './fixtures'
import {
  addComment,
  answerTicket,
  claimTicket,
  createTicket,
  openTicket,
  uniqueText,
  updateStatus,
} from './workflow'

test('営業とサポートが報告書と客先同行を別チケットで完了できる @full-regression', async ({
  salesPage,
  supportPage,
}) => {
  for (const tracker of ['報告書', '客先同行'] as const) {
    const ticket = await createTicket(salesPage, uniqueText(`E2E-${tracker}-full-regression`), tracker)

    await claimTicket(supportPage, ticket.id, ticket.subject)
    await addComment(supportPage, uniqueText(`${tracker}-サポートコメント`))
    await answerTicket(supportPage, uniqueText(`${tracker}-サポート回答`))

    await openTicket(salesPage, ticket.id, ticket.subject)
    await addComment(salesPage, uniqueText(`${tracker}-営業クローズ確認コメント`))
    await updateStatus(salesPage, 'クローズ待ち')

    await openTicket(supportPage, ticket.id, ticket.subject)
    await addComment(supportPage, uniqueText(`${tracker}-サポートクローズコメント`))
    await updateStatus(supportPage, 'クローズ')
  }
})
