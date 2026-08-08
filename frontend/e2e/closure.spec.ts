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

test('営業のクローズ待ちからサポートがクローズできる @closure', async ({ salesPage, supportPage }) => {
  const ticket = await createTicket(salesPage)
  await claimTicket(supportPage, ticket.id, ticket.subject)
  await answerTicket(supportPage, uniqueText('クローズ前回答'))

  await openTicket(salesPage, ticket.id, ticket.subject)
  await addComment(salesPage, uniqueText('営業確認コメント'))
  await updateStatus(salesPage, 'クローズ待ち')

  await openTicket(supportPage, ticket.id, ticket.subject)
  await addComment(supportPage, uniqueText('クローズコメント'))
  await updateStatus(supportPage, 'クローズ')
})
