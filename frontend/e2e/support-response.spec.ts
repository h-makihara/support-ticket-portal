import { test } from './fixtures'
import { addComment, answerTicket, claimTicket, createTicket, uniqueText } from './workflow'

test('サポート担当が担当・コメント・回答できる @support-response', async ({ salesPage, supportPage }) => {
  const ticket = await createTicket(salesPage)

  await claimTicket(supportPage, ticket.id, ticket.subject)
  await addComment(supportPage, uniqueText('サポートコメント'))
  await answerTicket(supportPage, uniqueText('サポート回答'))
})
