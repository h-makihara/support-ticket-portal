import { test, expect } from "./fixtures";
import { createTicket, uniqueText } from "./workflow";

for (const tracker of ["報告書", "客先同行"] as const) {
  test(`営業担当が「${tracker}」依頼内容のチケットを作成できる @requirements`, async ({
    salesPage,
  }) => {
    const ticket = await createTicket(
      salesPage,
      uniqueText(`E2E-${tracker}`),
      tracker,
    );

    await expect(
      salesPage.getByText(`依頼内容: ${tracker}`, { exact: true }),
    ).toBeVisible();
    if (tracker === "客先同行") {
      await expect(
        salesPage.getByText("同行方法: オンライン", { exact: true }),
      ).toBeVisible();
    }
    await salesPage.goto("/");
    const row = salesPage.getByRole("row").filter({ hasText: ticket.subject });
    await expect(row).toContainText(tracker);
  });
}
