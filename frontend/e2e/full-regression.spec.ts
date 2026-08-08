import { test } from './fixtures'
import {
  addComment,
  answerTicket,
  claimTicket,
  createTicket,
  enableRequirement,
  openTicket,
  uniqueText,
  updateStatus,
} from './workflow'

test('営業とサポートの問い合わせライフサイクル全体 @full-regression', async ({
  salesPage,
  supportPage,
}) => {
  // 1. 営業担当でログインして新規チケット作成
  const ticket = await createTicket(salesPage, uniqueText('E2E-full-regression'))

  // 2-4. サポート担当が担当、コメント、回答
  await claimTicket(supportPage, ticket.id, ticket.subject)
  await addComment(supportPage, uniqueText('第1サポートコメント'))
  await answerTicket(supportPage, uniqueText('第1サポート回答'))

  // 5. 営業担当が報告書要否を反映
  await openTicket(salesPage, ticket.id, ticket.subject)
  await enableRequirement(salesPage, '報告書が必要')

  // 6-7. サポート担当が再度担当、コメント、回答
  await claimTicket(supportPage, ticket.id, ticket.subject)
  await addComment(supportPage, uniqueText('第2サポートコメント'))
  await answerTicket(supportPage, uniqueText('第2サポート回答'))

  // 8. 営業担当が客先同行要否を反映
  await openTicket(salesPage, ticket.id, ticket.subject)
  await enableRequirement(salesPage, '客先同行が必要')

  // 9-10. サポート担当が再度担当、コメント、回答
  await claimTicket(supportPage, ticket.id, ticket.subject)
  await addComment(supportPage, uniqueText('第3サポートコメント'))
  await answerTicket(supportPage, uniqueText('第3サポート回答'))

  // 11-12. 営業担当がコメントし、クローズ待ちへ変更
  await openTicket(salesPage, ticket.id, ticket.subject)
  await addComment(salesPage, uniqueText('営業クローズ確認コメント'))
  await updateStatus(salesPage, 'クローズ待ち')

  // 13. サポート担当がコメントし、クローズへ変更
  await openTicket(supportPage, ticket.id, ticket.subject)
  await addComment(supportPage, uniqueText('サポートクローズコメント'))
  await updateStatus(supportPage, 'クローズ')
})
