import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  getTicket,
  addComment,
  answerTicket,
  updateStatus,
  updatePriority,
  updateTicketCustomFields,
  getTicketStatusOptions,
  getTicketPriorityOptions,
  AuthUser,
  Ticket,
  TicketStatusOption,
  TicketPriorityOption,
  AuditEntry,
  TicketCustomFields,
  VisitMode,
} from "../api/client";
import {
  normalizePriorityName,
  priorityBadgeClass,
  priorityLabel,
} from "../priority";
import { AuditLog } from "../components/AuditLog";
import { hasCapability } from "../authz";

export function TicketDetail({ user }: { user: AuthUser }) {
  const { id } = useParams<{ id: string }>();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [comment, setComment] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusOptions, setStatusOptions] = useState<TicketStatusOption[]>([]);
  const [priorityOptions, setPriorityOptions] = useState<
    TicketPriorityOption[]
  >([]);
  const [submitting, setSubmitting] = useState(false);
  const [customFields, setCustomFields] = useState<TicketCustomFields | null>(
    null,
  );

  const loadTicketData = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [t, opts, priorities] = await Promise.all([
        getTicket(parseInt(id)),
        getTicketStatusOptions(),
        getTicketPriorityOptions(),
      ]);
      setTicket(t);
      setCustomFields({
        customer_id: t.customer_id,
        ...(t.tracker === "report"
          ? { report_delivered: t.report_delivered }
          : {}),
        ...(t.tracker === "customer_visit"
          ? { schedule_assigned: t.schedule_assigned, visit_mode: t.visit_mode }
          : {}),
      });
      setAuditLog(t.audit_log ?? []);
      const options = opts.length > 0 ? opts : [{ id: 0, label: t.status }];
      setStatusOptions(options);
      const current = options.find((opt) => opt.label === t.status);
      setStatus(String(current?.id ?? options[0]?.id ?? ""));
      setPriorityOptions(priorities);
      setPriority(String(t.priority));
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "チケットの取得に失敗しました";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTicketData();
  }, [id]);

  const handleComment = async () => {
    if (!id || !comment.trim()) return;
    setSubmitting(true);
    try {
      await addComment(parseInt(id), comment);
      setComment("");
      setError(null); // Clear any previous error on success.
      await loadTicketData();
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "コメントの追加に失敗しました";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleAnswer = async () => {
    if (!id || !comment.trim()) return;
    setSubmitting(true);
    try {
      await answerTicket(parseInt(id), comment);
      setComment("");
      setError(null);
      await loadTicketData();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "回答の追加に失敗しました";
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatus = async (statusId: number) => {
    if (!id) return;
    try {
      await updateStatus(parseInt(id), statusId);
      setError(null); // Clear any previous error on success.
      await loadTicketData();
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "ステータスの変更に失敗しました";
      setError(msg);
    }
  };

  const handlePriority = async (priorityId: number) => {
    if (!id) return;
    setSubmitting(true);
    try {
      await updatePriority(parseInt(id), priorityId);
      setError(null);
      await loadTicketData();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "優先度の変更に失敗しました");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCustomFields = async () => {
    if (!id || !customFields) return;
    setSubmitting(true);
    try {
      await updateTicketCustomFields(parseInt(id), customFields);
      setError(null);
      await loadTicketData();
    } catch (e: unknown) {
      setError(
        e instanceof Error
          ? e.message
          : "カスタムフィールドの更新に失敗しました",
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <div className="loading">読み込み中...</div>;

  // Loading error state with retry button.
  if (!ticket && error) {
    return (
      <div>
        <Link to="/" style={{ display: "inline-block", marginBottom: "1rem" }}>
          ← 一覧に戻る
        </Link>
        <div
          style={{
            padding: "1rem",
            backgroundColor: "#ffeaea",
            border: "1px solid #ffcccc",
            borderRadius: "4px",
          }}
        >
          <strong>エラー:</strong> {error}
          <button
            className="btn btn-secondary"
            onClick={loadTicketData}
            style={{ marginLeft: "0.5rem" }}
          >
            再試行
          </button>
        </div>
      </div>
    );
  }

  if (!ticket) return <div className="empty">チケットが見つかりません</div>;

  return (
    <div>
      <Link to="/" style={{ display: "inline-block", marginBottom: "1rem" }}>
        ← 一覧に戻る
      </Link>

      {/* Error Banner */}
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
            onClick={loadTicketData}
            style={{ marginLeft: "0.5rem" }}
          >
            再試行
          </button>
        </div>
      )}

      {/* Ticket info card */}
      <div className="card">
        <h1>{ticket.subject}</h1>
        <div style={{ marginTop: "1rem", color: "#666" }}>
          <strong>ID:</strong> {ticket.id} | <strong>ステータス:</strong>{" "}
          {ticket.status} | <strong>優先度:</strong>{" "}
          <span className={priorityBadgeClass(ticket)}>
            {priorityLabel(ticket)}
          </span>{" "}
          | <span>依頼内容: {ticket.tracker_name}</span>
        </div>
        <div className="ticket-assignee">
          <span>対応者</span>
          <strong>{ticket.assignee?.name || "未割り当て"}</strong>
        </div>
        <div style={{ marginTop: "1rem", whiteSpace: "pre-wrap" }}>
          {ticket.description}
        </div>
      </div>

      {customFields && (
        <div className="card custom-fields-card">
          <h3>対応情報</h3>
          <div className="form-group">
            <label htmlFor="customer-id">顧客ID</label>
            <input
              id="customer-id"
              type="text"
              value={customFields.customer_id}
              onChange={(e) =>
                setCustomFields({
                  ...customFields,
                  customer_id: e.target.value,
                })
              }
            />
          </div>
          {ticket.tracker === "customer_visit" &&
            (user.roles.includes("support") ? (
              <div className="form-group">
                <label htmlFor="visit-mode">同行方法</label>
                <select
                  id="visit-mode"
                  value={customFields.visit_mode ?? ""}
                  onChange={(e) =>
                    setCustomFields({
                      ...customFields,
                      visit_mode: e.target.value as VisitMode,
                    })
                  }
                  required
                >
                  <option value="">選択してください</option>
                  <option value="オンライン">オンライン</option>
                  <option value="オフライン">オフライン</option>
                </select>
              </div>
            ) : (
              <p>同行方法: {ticket.visit_mode || "未設定"}</p>
            ))}
          <div className="custom-field-checks">
            {user.roles.includes("support") && ticket.tracker === "report" && (
              <label>
                <input
                  type="checkbox"
                  checked={customFields.report_delivered ?? false}
                  onChange={(e) =>
                    setCustomFields({
                      ...customFields,
                      report_delivered: e.target.checked,
                    })
                  }
                />{" "}
                報告書を渡した
              </label>
            )}
            {user.roles.includes("support") &&
              ticket.tracker === "customer_visit" && (
                <label>
                  <input
                    type="checkbox"
                    checked={customFields.schedule_assigned ?? false}
                    onChange={(e) =>
                      setCustomFields({
                        ...customFields,
                        schedule_assigned: e.target.checked,
                      })
                    }
                  />{" "}
                  予定・担当者をアサインした
                </label>
              )}
          </div>
          <button
            className="btn btn-success"
            onClick={handleCustomFields}
            disabled={
              submitting ||
              (ticket.tracker === "customer_visit" && !customFields.visit_mode)
            }
          >
            対応情報を更新
          </button>
        </div>
      )}

      {/* Full audit log with comments + field changes */}
      <AuditLog entries={auditLog} />

      {/* Comment form */}
      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>コメント追加</h3>
        {error && (
          <div style={{ color: "#e74c3c", marginBottom: "0.5rem" }}>
            {error}
          </div>
        )}
        <div className="form-group">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="コメントを入力..."
          />
        </div>
        <div className="comment-actions">
          <button
            className="btn btn-primary"
            onClick={handleComment}
            disabled={!comment.trim() || submitting}
          >
            送信
          </button>
          {hasCapability(user, "tickets:answer") && (
            <button
              className="btn btn-success"
              onClick={handleAnswer}
              disabled={!comment.trim() || submitting}
            >
              回答
            </button>
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>優先度変更</h3>
        <select
          value={priority}
          onChange={(e) => setPriority(e.target.value)}
          style={{
            padding: "0.5rem",
            borderRadius: "4px",
            border: "1px solid #ddd",
            marginRight: "0.5rem",
          }}
        >
          {priorityOptions.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {normalizePriorityName(opt.label)}
            </option>
          ))}
        </select>
        <button
          className="btn btn-success"
          onClick={() => handlePriority(parseInt(priority))}
          disabled={
            !priority || submitting || parseInt(priority) === ticket.priority
          }
        >
          更新
        </button>
      </div>

      {/* Status change form */}
      <div className="card" style={{ marginTop: "1rem" }}>
        <h3>ステータス変更</h3>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          style={{
            padding: "0.5rem",
            borderRadius: "4px",
            border: "1px solid #ddd",
            marginRight: "0.5rem",
          }}
        >
          {statusOptions.map((opt) => (
            <option key={opt.id} value={opt.id}>
              {opt.label}
            </option>
          ))}
        </select>
        <button
          className="btn btn-success"
          onClick={() => handleStatus(parseInt(status))}
          disabled={!status || parseInt(status) === 0}
        >
          更新
        </button>
      </div>
    </div>
  );
}
