import { useEffect, useState, type SubmitEvent } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  AuthUser,
  createTicket,
  getTicketPriorityOptions,
  TicketPriorityOption,
  TrackerKey,
  VisitMode,
} from "../api/client";
import { normalizePriorityName } from "../priority";

export function TicketCreate({ user }: { user: AuthUser }) {
  const navigate = useNavigate();
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<number | null>(null);
  const [priorityOptions, setPriorityOptions] = useState<
    TicketPriorityOption[]
  >([]);
  const [customerId, setCustomerId] = useState("");
  const [tracker, setTracker] = useState<TrackerKey>("inquiry");
  const [reportDelivered, setReportDelivered] = useState(false);
  const [scheduleAssigned, setScheduleAssigned] = useState(false);
  const [visitMode, setVisitMode] = useState<VisitMode | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getTicketPriorityOptions()
      .then((options) => {
        setPriorityOptions(options);
        setPriority(
          options.find((option) => option.is_default)?.id ??
            options[0]?.id ??
            null,
        );
      })
      .catch((e) =>
        setError(
          e instanceof Error ? e.message : "優先度設定の取得に失敗しました",
        ),
      );
  }, []);

  const handleSubmit = async (e: SubmitEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (
      !subject.trim() ||
      !description.trim() ||
      priority === null ||
      (tracker === "customer_visit" && !visitMode)
    ) {
      setError(
        priority === null
          ? "優先度を選択してください"
          : tracker === "customer_visit" && !visitMode
            ? "同行方法を選択してください"
            : "件名と本文は必須です",
      );
      return;
    }
    setLoading(true);
    setError(null); // Clear previous errors on new submit
    try {
      const ticket = await createTicket({
        tracker,
        subject,
        description,
        priority,
        customer_id: customerId,
        ...(tracker === "report" ? { report_delivered: reportDelivered } : {}),
        ...(tracker === "customer_visit"
          ? { schedule_assigned: scheduleAssigned, visit_mode: visitMode as VisitMode }
          : {}),
      });
      navigate(`/tickets/${ticket.id}`);
    } catch (e: unknown) {
      const msg =
        e instanceof Error ? e.message : "チケットの作成に失敗しました";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Link
        to="/"
        style={{
          display: "inline-block",
          marginBottom: "1rem",
          color: "#3498db",
          textDecoration: "none",
        }}
      >
        ← 一覧に戻る
      </Link>

      <div className="card">
        <h1>新規チケット作成</h1>

        {/* Error State with retry option */}
        {error && (
          <div
            style={{
              padding: "0.8rem",
              backgroundColor: "#ffeaea",
              border: "1px solid #ffcccc",
              borderRadius: "4px",
              marginTop: "1rem",
            }}
          >
            <strong>エラー:</strong> {error}
          </div>
        )}

        <form onSubmit={handleSubmit} style={{ marginTop: "1rem" }}>
          <div className="form-group">
            <label htmlFor="tracker">依頼内容</label>
            <select
              id="tracker"
              value={tracker}
              onChange={(e) => setTracker(e.target.value as TrackerKey)}
              disabled={loading}
            >
              <option value="inquiry">問い合わせ</option>
              <option value="report">報告書</option>
              <option value="customer_visit">客先同行</option>
            </select>
          </div>

          <div className="form-group">
            <label>件名</label>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="件名を入力..."
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>本文</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="問い合わせ内容を入力..."
              rows={8}
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label>優先度</label>
            <select
              value={priority ?? ""}
              onChange={(e) => setPriority(parseInt(e.target.value))}
              disabled={loading}
            >
              {priorityOptions.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {normalizePriorityName(opt.label)}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="customer-id">顧客ID</label>
            <input
              id="customer-id"
              type="text"
              value={customerId}
              onChange={(e) => setCustomerId(e.target.value)}
              disabled={loading}
            />
          </div>

          {tracker === "customer_visit" && (
            <div className="form-group">
              <label htmlFor="visit-mode">同行方法</label>
              <select
                id="visit-mode"
                value={visitMode}
                onChange={(e) => setVisitMode(e.target.value as VisitMode | "")}
                disabled={loading}
                required
              >
                <option value="">選択してください</option>
                <option value="オンライン">オンライン</option>
                <option value="オフライン">オフライン</option>
              </select>
            </div>
          )}

          <div className="custom-field-checks">
            {user.roles.includes("support") && tracker === "report" && (
              <label>
                <input
                  type="checkbox"
                  checked={reportDelivered}
                  onChange={(e) => setReportDelivered(e.target.checked)}
                  disabled={loading}
                />{" "}
                報告書を渡した
              </label>
            )}
            {user.roles.includes("support") && tracker === "customer_visit" && (
              <label>
                <input
                  type="checkbox"
                  checked={scheduleAssigned}
                  onChange={(e) => setScheduleAssigned(e.target.checked)}
                  disabled={loading}
                />{" "}
                予定・担当者をアサインした
              </label>
            )}
          </div>

          <button
            className="btn btn-primary"
            type="submit"
            disabled={
              loading ||
              priority === null ||
              !subject.trim() ||
              !description.trim() ||
              (tracker === "customer_visit" && !visitMode)
            }
          >
            {loading ? "作成中..." : "作成する"}
          </button>
        </form>
      </div>
    </div>
  );
}
