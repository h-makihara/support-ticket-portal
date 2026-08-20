import { test, expect } from './fixtures'
import { uniqueText } from './workflow'

const SAMPLE_QUESTION = '報告書が欲しいです'
const SAMPLE_ANSWER = '報告書チケットを作成し、対応情報を更新してください'

test('営業担当が初期FAQを検索して詳細を表示できる @faq', async ({ salesPage }) => {
  await salesPage.goto('/faqs')
  await expect(salesPage.getByRole('heading', { name: 'FAQ', exact: true })).toBeVisible()
  await expect(salesPage.getByRole('link', { name: 'FAQを作成' })).not.toBeVisible()

  await salesPage.getByLabel('FAQを検索').fill(SAMPLE_QUESTION)
  await salesPage.getByRole('button', { name: '検索' }).click()
  await salesPage.getByRole('link', { name: SAMPLE_QUESTION, exact: true }).click()

  await expect(salesPage.getByRole('heading', { name: SAMPLE_QUESTION })).toBeVisible()
  await expect(salesPage.getByText(SAMPLE_ANSWER, { exact: true })).toBeVisible()
  await expect(salesPage.getByRole('link', { name: '編集' })).not.toBeVisible()
  await expect(salesPage.getByRole('button', { name: '削除' })).not.toBeVisible()
})

test('サポート担当がFAQを作成・編集・削除できる @faq', async ({ supportPage }) => {
  const question = uniqueText('E2E-FAQ-報告書')
  const updatedQuestion = `${question}-更新済み`

  await supportPage.goto('/faqs')
  await supportPage.getByRole('link', { name: 'FAQを作成' }).click()
  await supportPage.getByLabel('質問').fill(question)
  await supportPage.getByLabel('回答').fill(SAMPLE_ANSWER)
  await supportPage.getByRole('button', { name: '保存する' }).click()
  await expect(supportPage.getByRole('heading', { name: question })).toBeVisible()

  await supportPage.getByRole('link', { name: '編集' }).click()
  await supportPage.getByLabel('質問').fill(updatedQuestion)
  await supportPage.getByRole('button', { name: '保存する' }).click()
  await expect(supportPage.getByRole('heading', { name: updatedQuestion })).toBeVisible()

  await supportPage.getByRole('button', { name: '削除' }).click()
  const dialog = supportPage.getByRole('dialog', { name: 'FAQを削除しますか？' })
  await dialog.getByRole('button', { name: '削除する' }).click()
  await expect(supportPage).toHaveURL(/\/faqs$/)
  await supportPage.getByLabel('FAQを検索').fill(updatedQuestion)
  await supportPage.getByRole('button', { name: '検索' }).click()
  await expect(supportPage.getByText('該当するFAQがありません')).toBeVisible()
})

test('管理者がFAQを作成・削除できる @faq', async ({ adminPage }) => {
  const question = uniqueText('E2E-管理者FAQ')

  await adminPage.goto('/faqs')
  await adminPage.getByRole('link', { name: 'FAQを作成' }).click()
  await adminPage.getByLabel('質問').fill(question)
  await adminPage.getByLabel('回答').fill(SAMPLE_ANSWER)
  await adminPage.getByRole('button', { name: '保存する' }).click()
  await expect(adminPage.getByRole('heading', { name: question })).toBeVisible()

  await adminPage.getByRole('button', { name: '削除' }).click()
  await adminPage.getByRole('dialog', { name: 'FAQを削除しますか？' }).getByRole('button', { name: '削除する' }).click()
  await expect(adminPage).toHaveURL(/\/faqs$/)
})
