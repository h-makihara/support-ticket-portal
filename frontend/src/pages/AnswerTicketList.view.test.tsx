// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Ticket } from "../api/client";

const { getTicketsMock } = vi.hoisted(() => ({ getTicketsMock: vi.fn() }));
vi.mock("../api/client", () => ({
  claimTicket: vi.fn(),
  getTickets: getTicketsMock,
}));

import { AnswerTicketList } from "./AnswerTicketList";

function ticket(
  id: number,
  tracker: Ticket["tracker"],
  trackerName: string,
): Ticket {
  return {
    id,
    subject: `チケット${id}`,
    description: "",
    status: "対応待ち",
    priority: 1,
    priority_name: "通常",
    tracker,
    tracker_name: trackerName,
    assignee: null,
    customer_id: "",
  };
}

beforeEach(() => {
  getTicketsMock.mockReset();
  getTicketsMock.mockResolvedValue({
    tickets: [
      ticket(1, "report", "報告書"),
      ticket(2, "inquiry", "問い合わせ"),
      ticket(3, "report", "報告書"),
    ],
    pagination: { limit: 20, offset: 0, total_count: 3, has_more: false },
  });
});

describe("回答者向け一覧の依頼内容別表示", () => {
  it("依頼内容ごとのセクションに元の順序でチケットを表示する", async () => {
    render(
      <MemoryRouter>
        <AnswerTicketList />
      </MemoryRouter>,
    );

    const reportGroup = await screen.findByRole("region", { name: "報告書" });
    const inquiryGroup = screen.getByRole("region", { name: "問い合わせ" });

    expect(within(reportGroup).getAllByRole("row")).toHaveLength(3);
    expect(within(reportGroup).getByText("チケット1")).toBeVisible();
    expect(within(reportGroup).getByText("チケット3")).toBeVisible();
    expect(within(inquiryGroup).getAllByRole("row")).toHaveLength(2);
    expect(within(inquiryGroup).getByText("チケット2")).toBeVisible();
  });
});
