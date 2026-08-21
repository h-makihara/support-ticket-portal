import { useState, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  claimTicket,
  getTickets,
  Ticket,
  TicketListResponse,
} from "../api/client";
import { priorityBadgeClass, priorityLabel } from "../priority";

const PAGE_SIZE = 20;
const ONE_DAY_MS = 24 * 60 * 60 * 1000;

export function isUpdatedAtLeastOneDayAgo(
  updatedOn: string | undefined,
  now: number = Date.now(),
): boolean {
  if (!updatedOn) return false;
  const updatedAt = new Date(updatedOn).getTime();
  return Number.isFinite(updatedAt) && now - updatedAt >= ONE_DAY_MS;
}

export function formatUpdatedOn(updatedOn: string | undefined): string {
  if (!updatedOn) return "-";
  const date = new Date(updatedOn);
  if (!Number.isFinite(date.getTime())) return "-";
  return date.toLocaleString("ja-JP", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function AnswerTicketList() {
  const navigate = useNavigate();
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ticketToClaim, setTicketToClaim] = useState<Ticket | null>(null);
  const [claiming, setClaiming] = useState(false);

  const loadTickets = async () => {
    setLoading(true);
    setError(null);
    try {
      const resp: TicketListResponse = await getTickets({
        responderView: true,
        limit: PAGE_SIZE,
        offset,
      });
      setTickets(resp.tickets);
      setTotalCount(resp.pagination.total_count);
      setHasMore(resp.pagination.has_more);
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "チケットの取得に失敗しました";
      setError(msg);
      setTickets([]);
      setTotalCount(0);
      setHasMore(false);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTickets();
  }, [offset]);

  const goToPage = (page: number) => {
    setOffset(page * PAGE_SIZE);
  };

  const handleClaim = async () => {
    if (!ticketToClaim) return;
    setClaiming(true);
    setError(null);
    try {
      await claimTicket(ticketToClaim.id);
      navigate(`/tickets/${ticketToClaim.id}`);
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "担当者の割り当てに失敗しました";
      setError(msg);
      setTicketToClaim(null);
    } finally {
      setClaiming(false);
    }
  };

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const currentPage = Math.floor(offset / PAGE_SIZE);

  if (loading) return <div className="loading">読み込み中...</div>;

  return (
    <div>
      <h1 style={{ marginBottom: "1rem" }}>回答者向けチケット一覧</h1>
      <div style={{ color: "#666", fontSize: "0.9rem", marginBottom: "1rem" }}>
        対応すべきチケット: {totalCount} 件
      </div>

      {/* Error State */}
      {error && (
        <div
          style={{
            padding: "0.8rem",
            backgroundColor: "#ffeaea",
            border: "1px solid #ffcccc",
            borderRadius: "4px",
            marginBottom: "1rem",
          }}
        >
          <strong>エラー:</strong> {error}
          <button
            className="btn btn-secondary"
            onClick={loadTickets}
            style={{ marginLeft: "0.5rem" }}
          >
            再試行
          </button>
        </div>
      )}

      {tickets.length === 0 ? (
        <div className="empty">対応すべきチケットはありません</div>
      ) : (
        <>
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>件名</th>
                <th>依頼内容</th>
                <th>ステータス</th>
                <th>優先度</th>
                <th>対応者</th>
                <th>前回担当</th>
                <th>作成日</th>
                <th>最終更新日</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((ticket) => (
                <tr key={ticket.id}>
                  <td>{ticket.id}</td>
                  <td>
                    <Link to={`/tickets/${ticket.id}`}>{ticket.subject}</Link>
                  </td>
                  <td>{ticket.tracker_name}</td>
                  <td>
                    <span
                      className={`status-badge status-${ticket.status.toLowerCase().replace(/\s+/g, "_")}`}
                    >
                      {ticket.status}
                    </span>
                  </td>
                  <td>
                    <span className={priorityBadgeClass(ticket)}>
                      {priorityLabel(ticket)}
                    </span>
                  </td>
                  <td>{ticket.assignee?.name || "未割り当て"}</td>
                  <td>{ticket.latest_support_responder?.name || "—"}</td>
                  <td>
                    {ticket.created_on
                      ? new Date(ticket.created_on).toLocaleDateString()
                      : "-"}
                  </td>
                  <td
                    className={
                      isUpdatedAtLeastOneDayAgo(ticket.updated_on)
                        ? "ticket-updated-overdue"
                        : undefined
                    }
                  >
                    {formatUpdatedOn(ticket.updated_on)}
                  </td>
                  <td>
                    <button
                      className="btn btn-primary"
                      style={{ padding: "0.5rem 1rem" }}
                      onClick={() => setTicketToClaim(ticket)}
                    >
                      対応する
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div
              style={{
                display: "flex",
                justifyContent: "center",
                gap: "0.5rem",
                marginTop: "1rem",
                flexWrap: "wrap",
              }}
            >
              <button
                className="btn btn-secondary"
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 0}
                style={{ padding: "0.4rem 0.8rem" }}
              >
                ← 前へ
              </button>

              {[...Array(totalPages)].map((_, i) => (
                <button
                  key={i}
                  className={`btn ${i === currentPage ? "btn-primary" : "btn-secondary"}`}
                  onClick={() => goToPage(i)}
                  style={{ padding: "0.4rem 0.8rem", minWidth: "2rem" }}
                >
                  {i + 1}
                </button>
              ))}

              <button
                className="btn btn-secondary"
                onClick={() => goToPage(currentPage + 1)}
                disabled={!hasMore}
                style={{ padding: "0.4rem 0.8rem" }}
              >
                次へ →
              </button>
            </div>
          )}
        </>
      )}

      {ticketToClaim && (
        <div
          className="modal-backdrop"
          role="presentation"
          onMouseDown={() => !claiming && setTicketToClaim(null)}
        >
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="claim-dialog-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <h2 id="claim-dialog-title">このチケットに対応しますか？</h2>
            <p>「{ticketToClaim.subject}」の対応者にあなたを割り当てます。</p>
            <div className="confirm-dialog-actions">
              <button
                className="btn btn-secondary"
                onClick={() => setTicketToClaim(null)}
                disabled={claiming}
              >
                キャンセル
              </button>
              <button
                className="btn btn-primary"
                onClick={handleClaim}
                disabled={claiming}
              >
                {claiming ? "割り当て中…" : "対応する"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
