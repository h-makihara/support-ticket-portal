// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Ticket } from "../api/client";
import { TicketDetail } from "./TicketDetail";

const {
  getTicketMock,
  getTicketPriorityOptionsMock,
  getTicketStatusOptionsMock,
  updateTicketCustomFieldsMock,
} = vi.hoisted(() => ({
  getTicketMock: vi.fn(),
  getTicketPriorityOptionsMock: vi.fn(),
  getTicketStatusOptionsMock: vi.fn(),
  updateTicketCustomFieldsMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  getTicket: getTicketMock,
  getTicketPriorityOptions: getTicketPriorityOptionsMock,
  getTicketStatusOptions: getTicketStatusOptionsMock,
  updateTicketCustomFields: updateTicketCustomFieldsMock,
}));

afterEach(cleanup);

const supportUser = {
  id: 1,
  username: "support",
  name: "サポート",
  roles: ["support"],
};

function ticket(tracker: Ticket["tracker"], trackerName: string): Ticket {
  return {
    id: 1,
    subject: "チケット",
    description: "本文",
    status: "新規",
    priority: 1,
    priority_name: "通常",
    tracker,
    tracker_name: trackerName,
    assignee: null,
    customer_id: "",
  };
}

function renderTicketDetail(user = supportUser) {
  render(
    <MemoryRouter initialEntries={["/tickets/1"]}>
      <Routes>
        <Route
          path="/tickets/:id"
          element={<TicketDetail user={user} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  getTicketMock.mockReset();
  getTicketStatusOptionsMock
    .mockReset()
    .mockResolvedValue([{ id: 1, label: "新規" }]);
  getTicketPriorityOptionsMock
    .mockReset()
    .mockResolvedValue([{ id: 1, label: "通常", is_default: true }]);
  updateTicketCustomFieldsMock.mockReset().mockResolvedValue(undefined);
});

describe("TicketDetail tracker controls", () => {
  it("shows only the report completion control for report tickets", async () => {
    getTicketMock.mockResolvedValue(ticket("report", "報告書"));
    renderTicketDetail();

    expect(await screen.findByText("依頼内容: 報告書")).toBeVisible();
    expect(screen.getByLabelText("報告書を渡した")).toBeVisible();
    expect(
      screen.queryByLabelText("予定・担当者をアサインした"),
    ).not.toBeInTheDocument();
  });

  it("shows only the schedule completion control for customer-visit tickets", async () => {
    getTicketMock.mockResolvedValue({
      ...ticket("customer_visit", "客先同行"),
      visit_mode: "オンライン",
    });
    renderTicketDetail();

    expect(await screen.findByText("依頼内容: 客先同行")).toBeVisible();
    expect(screen.queryByLabelText("報告書を渡した")).not.toBeInTheDocument();
    expect(screen.getByLabelText("予定・担当者をアサインした")).toBeVisible();
    expect(screen.getByLabelText("同行方法")).toHaveValue("オンライン");

    fireEvent.change(screen.getByLabelText("同行方法"), {
      target: { value: "オフライン" },
    });
    fireEvent.click(screen.getByRole("button", { name: "対応情報を更新" }));

    await waitFor(() =>
      expect(updateTicketCustomFieldsMock).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ visit_mode: "オフライン" }),
      ),
    );
  });

  it("shows the visit mode as text to sales users", async () => {
    getTicketMock.mockResolvedValue({
      ...ticket("customer_visit", "客先同行"),
      visit_mode: "オフライン",
    });
    renderTicketDetail({
      id: 2,
      username: "sales",
      name: "営業",
      roles: ["sales"],
    });

    expect(await screen.findByText("同行方法: オフライン")).toBeVisible();
    expect(screen.queryByLabelText("同行方法")).not.toBeInTheDocument();
  });

  it("lets support update customer visit schedule preferences", async () => {
    getTicketMock.mockResolvedValue({
      ...ticket("customer_visit", "客先同行"),
      visit_mode: "オンライン",
      preferred_start_at_1: "2026-09-01 10:00",
      preferred_start_at_2: "2026-09-02 14:30",
      meeting_duration_minutes: 60,
    });
    renderTicketDetail();

    fireEvent.change(await screen.findByLabelText("開始希望日時 第一希望"), {
      target: { value: "2026-09-03 09:00" },
    });
    fireEvent.change(screen.getByLabelText("予定会議時間（分）"), {
      target: { value: "90" },
    });
    fireEvent.click(screen.getByRole("button", { name: "対応情報を更新" }));

    await waitFor(() =>
      expect(updateTicketCustomFieldsMock).toHaveBeenCalledWith(
        1,
        expect.objectContaining({
          preferred_start_at_1: "2026-09-03 09:00",
          preferred_start_at_2: "2026-09-02 14:30",
          meeting_duration_minutes: 90,
        }),
      ),
    );
  });

  it("shows customer visit schedule preferences as text to sales users", async () => {
    getTicketMock.mockResolvedValue({
      ...ticket("customer_visit", "客先同行"),
      visit_mode: "オンライン",
      preferred_start_at_1: "2026-09-01 10:00",
      preferred_start_at_2: null,
      meeting_duration_minutes: 60,
    });
    renderTicketDetail({
      id: 2,
      username: "sales",
      name: "営業",
      roles: ["sales"],
    });

    expect(await screen.findByText("開始希望日時 第一希望: 2026-09-01 10:00")).toBeVisible();
    expect(screen.getByText("開始希望日時 第二希望: 未設定")).toBeVisible();
    expect(screen.getByText("予定会議時間: 60分")).toBeVisible();
    expect(screen.queryByLabelText("開始希望日時 第一希望")).not.toBeInTheDocument();
  });

  it.each(["オンライン", undefined])(
    "lets sales update customer ID without resending visit mode (%s)",
    async (visitMode) => {
      getTicketMock.mockResolvedValue({
        ...ticket("customer_visit", "客先同行"),
        visit_mode: visitMode,
      });
      renderTicketDetail({
        id: 2,
        username: "sales",
        name: "営業",
        roles: ["sales"],
      });

      fireEvent.change(await screen.findByLabelText("顧客ID"), {
        target: { value: "C-200" },
      });
      const updateButton = screen.getByRole("button", {
        name: "対応情報を更新",
      });
      expect(updateButton).toBeEnabled();
      fireEvent.click(updateButton);

      await waitFor(() =>
        expect(updateTicketCustomFieldsMock).toHaveBeenCalledWith(1, {
          customer_id: "C-200",
        }),
      );
    },
  );

  it("requires support users to select a missing visit mode before updating", async () => {
    getTicketMock.mockResolvedValue({
      ...ticket("customer_visit", "客先同行"),
      visit_mode: undefined,
    });
    renderTicketDetail();

    expect(await screen.findByLabelText("同行方法")).toBeRequired();
    expect(
      screen.getByRole("button", { name: "対応情報を更新" }),
    ).toBeDisabled();
  });

  it("shows neither completion control for inquiry tickets", async () => {
    getTicketMock.mockResolvedValue(ticket("inquiry", "問い合わせ"));
    renderTicketDetail();

    expect(await screen.findByText("依頼内容: 問い合わせ")).toBeVisible();
    expect(screen.queryByLabelText("報告書を渡した")).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText("予定・担当者をアサインした"),
    ).not.toBeInTheDocument();
  });
});
