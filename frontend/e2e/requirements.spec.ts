import { test } from './fixtures'
import {
  answerTicket,
  claimTicket,
  createTicket,
  enableRequirement,
  openTicket,
  uniqueText,
} from './workflow'

for (const requirement of ['報告書が必要', '客先同行が必要'] as const) {
  test(`営業担当が「${requirement}」を反映すると再対応待ちになる @requirements`, async ({
    salesPage,
    supportPage,
  }) => {
    const ticket = await createTicket(salesPage)
    await claimTicket(supportPage, ticket.id, ticket.subject)
    await answerTicket(supportPage, uniqueText('事前回答'))

    await openTicket(salesPage, ticket.id, ticket.subject)
    await enableRequirement(salesPage, requirement)
  })
}
