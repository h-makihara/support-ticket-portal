import { test as base, expect, Page } from '@playwright/test'
import { loadRootEnv } from './env'
import { login } from './workflow'

loadRootEnv()

type RolePageFixtures = {
  salesPage: Page
  supportPage: Page
  adminPage: Page
}

function credentials(role: 'SALES' | 'SUPPORT' | 'ADMIN') {
  const username = process.env[`E2E_${role}_USERNAME`] || process.env[`TEST_${role}_USERNAME`]
  const password = process.env[`E2E_${role}_PASSWORD`] || process.env[`TEST_${role}_PASSWORD`]
  if (!username || !password) {
    throw new Error(
      `${role} のE2E認証情報がありません。E2E_${role}_USERNAME/PASSWORD ` +
      `または TEST_${role}_USERNAME/PASSWORD を設定してください。`,
    )
  }
  return { username, password }
}

export const test = base.extend<RolePageFixtures>({
  salesPage: async ({ browser, baseURL }, use) => {
    const context = await browser.newContext({ baseURL })
    const page = await context.newPage()
    await login(page, credentials('SALES'))
    await use(page)
    await context.close()
  },
  supportPage: async ({ browser, baseURL }, use) => {
    const context = await browser.newContext({ baseURL })
    const page = await context.newPage()
    await login(page, credentials('SUPPORT'))
    await use(page)
    await context.close()
  },
  adminPage: async ({ browser, baseURL }, use) => {
    const context = await browser.newContext({ baseURL })
    const page = await context.newPage()
    await login(page, credentials('ADMIN'))
    await use(page)
    await context.close()
  },
})

export { expect }
