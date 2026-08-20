import { expect, Page } from '@playwright/test'

type LoginCredentials = { username: string; password: string }
export type TrackerLabel = '問い合わせ' | '報告書' | '客先同行'

export function uniqueText(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export async function login(page: Page, credentials: LoginCredentials) {
  await page.goto('/')
  await page.getByLabel('ユーザー名').fill(credentials.username)
  await page.getByLabel('パスワード').fill(credentials.password)
  await page.getByRole('button', { name: 'ログイン', exact: true }).click()
  await expect(page.getByRole('navigation', { name: 'メインナビゲーション' })).toBeVisible()
}

export async function selectTracker(page: Page, tracker: TrackerLabel) {
  await page.getByLabel('トラッカー', { exact: true }).selectOption({ label: tracker })
}

export async function createTicket(
  page: Page,
  subject = uniqueText('E2E-ticket'),
  tracker: TrackerLabel = '問い合わせ',
) {
  await page.goto('/create')
  await selectTracker(page, tracker)
  await page.getByPlaceholder('件名を入力...').fill(subject)
  await page.getByPlaceholder('問い合わせ内容を入力...').fill(`E2E本文: ${subject}`)
  await page.getByLabel('顧客ID').fill(uniqueText('customer'))
  await page.getByRole('button', { name: '作成する' }).click()
  await expect(page.getByRole('heading', { name: subject })).toBeVisible()

  const match = page.url().match(/\/tickets\/(\d+)/)
  if (!match) throw new Error(`作成後のURLからチケットIDを取得できませんでした: ${page.url()}`)
  return { id: Number(match[1]), subject }
}

export async function openTicket(page: Page, ticketId: number, subject: string) {
  await page.goto(`/tickets/${ticketId}`)
  await expect(page.getByRole('heading', { name: subject })).toBeVisible()
}

export async function claimTicket(page: Page, ticketId: number, subject: string) {
  await page.goto('/answer')
  const row = page.getByRole('row').filter({ hasText: subject })
  await expect(row).toBeVisible()
  await row.getByRole('button', { name: '対応する' }).click()
  const dialog = page.getByRole('dialog', { name: 'このチケットに対応しますか？' })
  await dialog.getByRole('button', { name: '対応する', exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`/tickets/${ticketId}$`))
  await expect(page.getByRole('heading', { name: subject })).toBeVisible()
  await expectStatus(page, '対応中')
}

export async function addComment(page: Page, body: string) {
  const textarea = page.getByPlaceholder('コメントを入力...')
  const sendButton = page.getByRole('button', { name: '送信', exact: true })
  await textarea.fill(body)
  await sendButton.click()
  await expect(page.getByText(body, { exact: true })).toBeVisible()
  await expect(async () => {
    await textarea.fill('E2E-ready-check')
    await expect(sendButton).toBeEnabled()
  }).toPass()
  await textarea.fill('')
}

export async function answerTicket(page: Page, body: string) {
  const textarea = page.getByPlaceholder('コメントを入力...')
  const answerButton = page.getByRole('button', { name: '回答', exact: true })
  await expect(async () => {
    await textarea.fill(body)
    await expect(answerButton).toBeEnabled()
  }).toPass()
  await answerButton.click()
  await expect(page.getByText(body, { exact: true })).toBeVisible()
  await expectStatus(page, '対応済')
}

export async function updateStatus(page: Page, label: 'クローズ待ち' | 'クローズ') {
  const card = page.locator('.card').filter({
    has: page.getByRole('heading', { name: 'ステータス変更' }),
  })
  await card.getByRole('combobox').selectOption({ label })
  // React の controlled select が state へ反映されてから更新する。
  await page.evaluate(() => new Promise<void>(resolve => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()))
  }))
  await card.getByRole('button', { name: '更新', exact: true }).click()
  await expectStatus(page, label)
}

export async function expectStatus(page: Page, label: string) {
  await expect(page.locator('.card').first()).toContainText(`ステータス: ${label}`)
}
