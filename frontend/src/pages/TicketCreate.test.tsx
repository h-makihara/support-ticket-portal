// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TicketCreate } from "./TicketCreate";

const { createTicketMock, getTicketPriorityOptionsMock } = vi.hoisted(() => ({
  createTicketMock: vi.fn(),
  getTicketPriorityOptionsMock: vi.fn(),
}));

vi.mock("../api/client", () => ({
  createTicket: createTicketMock,
  getTicketPriorityOptions: getTicketPriorityOptionsMock,
}));

afterEach(cleanup);

beforeEach(() => {
  createTicketMock.mockReset().mockResolvedValue({ id: 1 });
  getTicketPriorityOptionsMock
    .mockReset()
    .mockResolvedValue([{ id: 1, label: "通常", is_default: true }]);
});

describe("TicketCreate", () => {
  it("submits the selected tracker", async () => {
    render(
      <MemoryRouter>
        <TicketCreate
          user={{ id: 1, username: "sales", name: "営業", roles: ["sales"] }}
        />
      </MemoryRouter>,
    );

    await screen.findByRole("option", { name: "通常" });
    const tracker = screen.getByLabelText("依頼内容");
    expect(
      within(tracker)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["問い合わせ", "報告書", "客先同行"]);
    fireEvent.change(tracker, { target: { value: "report" } });
    fireEvent.change(screen.getByPlaceholderText("件名を入力..."), {
      target: { value: "月次報告書" },
    });
    fireEvent.change(screen.getByPlaceholderText("問い合わせ内容を入力..."), {
      target: { value: "作成してください" },
    });
    fireEvent.click(screen.getByRole("button", { name: "作成する" }));

    await waitFor(() =>
      expect(createTicketMock).toHaveBeenCalledWith(
        expect.objectContaining({
          tracker: "report",
          subject: "月次報告書",
          description: "作成してください",
        }),
      ),
    );
  });

  it("requires and submits a visit mode for customer visits", async () => {
    render(
      <MemoryRouter>
        <TicketCreate
          user={{ id: 1, username: "sales", name: "営業", roles: ["sales"] }}
        />
      </MemoryRouter>,
    );

    await screen.findByRole("option", { name: "通常" });
    fireEvent.change(screen.getByLabelText("依頼内容"), {
      target: { value: "customer_visit" },
    });
    const visitMode = screen.getByLabelText("同行方法");
    expect(visitMode).toBeRequired();
    expect(
      within(visitMode)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["選択してください", "オンライン", "オフライン"]);

    fireEvent.change(visitMode, { target: { value: "オフライン" } });
    fireEvent.change(screen.getByPlaceholderText("件名を入力..."), {
      target: { value: "客先同行" },
    });
    fireEvent.change(screen.getByPlaceholderText("問い合わせ内容を入力..."), {
      target: { value: "現地でお願いします" },
    });
    fireEvent.click(screen.getByRole("button", { name: "作成する" }));

    await waitFor(() =>
      expect(createTicketMock).toHaveBeenCalledWith(
        expect.objectContaining({
          tracker: "customer_visit",
          visit_mode: "オフライン",
        }),
      ),
    );
  });

  it("submits optional customer visit schedule preferences", async () => {
    render(
      <MemoryRouter>
        <TicketCreate
          user={{ id: 1, username: "sales", name: "営業", roles: ["sales"] }}
        />
      </MemoryRouter>,
    );

    await screen.findByRole("option", { name: "通常" });
    fireEvent.change(screen.getByLabelText("依頼内容"), {
      target: { value: "customer_visit" },
    });
    expect(screen.getByLabelText("開始希望日時 第一希望")).not.toBeRequired();
    expect(screen.getByLabelText("開始希望日時 第一希望")).toHaveAttribute(
      "placeholder",
      "例: 2026-08-26 14:30",
    );
    fireEvent.change(screen.getByLabelText("開始希望日時 第一希望"), {
      target: { value: "2026-09-01 10:00" },
    });
    fireEvent.change(screen.getByLabelText("開始希望日時 第二希望"), {
      target: { value: "2026-09-02 14:30" },
    });
    fireEvent.change(screen.getByLabelText("予定会議時間（分）"), {
      target: { value: "60" },
    });
    fireEvent.change(screen.getByLabelText("同行方法"), {
      target: { value: "オンライン" },
    });
    fireEvent.change(screen.getByPlaceholderText("件名を入力..."), {
      target: { value: "客先同行" },
    });
    fireEvent.change(screen.getByPlaceholderText("問い合わせ内容を入力..."), {
      target: { value: "訪問をお願いします" },
    });
    fireEvent.click(screen.getByRole("button", { name: "作成する" }));

    await waitFor(() =>
      expect(createTicketMock).toHaveBeenCalledWith(
        expect.objectContaining({
          preferred_start_at_1: "2026-09-01 10:00",
          preferred_start_at_2: "2026-09-02 14:30",
          meeting_duration_minutes: 60,
        }),
      ),
    );
  });
});
