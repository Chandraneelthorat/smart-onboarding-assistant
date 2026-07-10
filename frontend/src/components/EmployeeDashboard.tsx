import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPost } from "../api/client";
import { ChatPanel } from "./ChatPanel";

type ClosureAlert = { ticket_id: string; title: string; item: string };

type EmployeeProfile = Record<string, unknown>;

type Summary = {
  role: string;
  employee: EmployeeProfile;
  tickets: Array<Record<string, string>>;
  closed_ticket_alerts?: ClosureAlert[];
  meetings: Array<Record<string, string>>;
  leave_balance: string;
  leave_history_text: string;
  leave_requests: Array<Record<string, unknown>>;
};

type Tab = "overview" | "team" | "leave" | "tickets" | "meetings" | "chat";

const EMP_TAB_IDS = new Set<Tab>(["overview", "team", "leave", "tickets", "meetings", "chat"]);

function normalizeEmployeeTabParam(raw: string | undefined): Tab {
  if (raw && EMP_TAB_IDS.has(raw as Tab)) return raw as Tab;
  return "overview";
}

function ticketStatusLabel(status: string): string {
  return status === "Closed" ? "Resolved" : status;
}

const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "team", label: "Team" },
  { id: "leave", label: "Leave" },
  { id: "tickets", label: "Tickets" },
  { id: "meetings", label: "Meetings" },
  { id: "chat", label: "Chat" },
];

type DirectReportRow = { emp_id: string; name: string; email: string };

function directReportsFromProfile(emp: EmployeeProfile): DirectReportRow[] {
  const raw = emp["direct_reports"];
  if (!Array.isArray(raw)) return [];
  const out: DirectReportRow[] = [];
  for (const item of raw) {
    if (item == null || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const empId = String(row.emp_id ?? "").trim();
    if (!empId) continue;
    out.push({
      emp_id: empId,
      name: String(row.name ?? "").trim() || empId,
      email: String(row.email ?? "").trim(),
    });
  }
  return out;
}

export function EmployeeDashboard() {
  const { tab: tabParam } = useParams<{ tab: string }>();
  const navigate = useNavigate();
  const tab = normalizeEmployeeTabParam(tabParam);

  useEffect(() => {
    if (tabParam !== tab) {
      navigate(`/app/employee/${tab}`, { replace: true });
    }
  }, [tabParam, tab, navigate]);

  const [summary, setSummary] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [leaveMsg, setLeaveMsg] = useState<string | null>(null);
  const [ticketItem, setTicketItem] = useState("");
  const [ticketReason, setTicketReason] = useState("");
  const [ticketTitle, setTicketTitle] = useState("");
  const [ticketMsg, setTicketMsg] = useState<string | null>(null);
  const [closureAckBusy, setClosureAckBusy] = useState(false);
  const [closureAckErr, setClosureAckErr] = useState<string | null>(null);

  const refreshSummary = useCallback(async () => {
    const data = await apiGet<Summary>("/api/portal/summary");
    setSummary(data);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiGet<Summary>("/api/portal/summary");
        if (!cancelled) setSummary(data);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "Failed to load");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function dismissClosureAlerts() {
    setClosureAckErr(null);
    setClosureAckBusy(true);
    try {
      await apiPost<{ message: string }>("/api/portal/tickets/closure-notices/ack", {});
      await refreshSummary();
    } catch (e) {
      setClosureAckErr(e instanceof Error ? e.message : "Could not dismiss notice");
    } finally {
      setClosureAckBusy(false);
    }
  }

  async function submitLeave(e: React.FormEvent) {
    e.preventDefault();
    setLeaveMsg(null);
    try {
      const res = await apiPost<{ message: string }>("/api/portal/leave/request", {
        start_date: start,
        end_date: end,
        reason,
        message: message || null,
      });
      setLeaveMsg(res.message);
      await refreshSummary();
    } catch (e) {
      setLeaveMsg(e instanceof Error ? e.message : "Request failed");
    }
  }

  async function submitTicket(e: React.FormEvent) {
    e.preventDefault();
    setTicketMsg(null);
    try {
      const res = await apiPost<{ message: string }>("/api/portal/tickets", {
        item: ticketItem.trim(),
        reason: ticketReason.trim(),
        title: ticketTitle.trim() || null,
      });
      setTicketMsg(res.message);
      setTicketItem("");
      setTicketReason("");
      setTicketTitle("");
      await refreshSummary();
    } catch (e) {
      setTicketMsg(e instanceof Error ? e.message : "Could not create ticket");
    }
  }

  if (err) {
    return <p className="text-sm text-red-300">{err}</p>;
  }
  if (!summary) {
    return <p className="text-sm text-slate-400">Loading…</p>;
  }

  const emp = summary.employee;

  function empField(key: string): string {
    const v = emp[key];
    if (v == null || typeof v === "object") return "";
    const s = String(v).trim();
    return s !== "" ? s : "";
  }

  const reportMgrId = empField("manager_id");
  const reportMgrName = empField("manager_name");
  const leaderMgId = empField("people_leader_mgr_id");
  const leaderName = empField("people_leader_name");
  const directReports = directReportsFromProfile(emp);

  const closureAlerts = summary.closed_ticket_alerts ?? [];

  return (
    <div className="space-y-6 text-left">
      {closureAlerts.length > 0 && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4 backdrop-blur-[1px]"
          role="presentation"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="closure-notice-title"
            className="w-full max-w-md rounded-xl border border-slate-600 bg-slate-900 p-6 shadow-2xl shadow-black/40"
          >
            <h2 id="closure-notice-title" className="text-lg font-semibold text-slate-50">
              Your ticket was resolved
            </h2>
            <p className="mt-2 text-sm text-slate-400">
              {closureAlerts.length > 1
                ? "HR has resolved the following tickets for you. You can still review them under Tickets."
                : "HR has resolved the following ticket for you. You can still review it under Tickets."}
            </p>
            <ul className="mt-4 space-y-2 text-sm text-slate-200">
              {closureAlerts.map((a) => (
                <li
                  key={a.ticket_id}
                  className="rounded-lg border border-slate-700/80 bg-slate-950/60 px-3 py-2"
                >
                  <span className="font-mono text-violet-300">{a.ticket_id}</span>
                  <span className="text-slate-500"> — </span>
                  {a.title || a.item}
                </li>
              ))}
            </ul>
            {closureAckErr && (
              <p className="mt-3 text-sm text-red-300" role="alert">
                {closureAckErr}
              </p>
            )}
            <div className="mt-6 flex justify-end">
              <button
                type="button"
                onClick={dismissClosureAlerts}
                disabled={closureAckBusy}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {closureAckBusy ? "Saving…" : "OK"}
              </button>
            </div>
          </div>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            onClick={() => navigate(`/app/employee/${id}`)}
            className={`rounded-lg px-3 py-2 text-sm font-medium ${
              tab === id
                ? "bg-violet-600 text-white"
                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
          <h3 className="font-semibold text-slate-50">Profile</h3>
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-2">
            <dt className="text-slate-500">Name</dt>
            <dd>{String(emp.name ?? "")}</dd>
            <dt className="text-slate-500">Employee ID</dt>
            <dd className="font-mono">{String(emp.emp_id ?? "")}</dd>
            <dt className="text-slate-500">Reporting manager</dt>
            <dd>
              {reportMgrId || reportMgrName ? (
                <>
                  {reportMgrName ? <span>{reportMgrName}</span> : null}
                  {reportMgrName && reportMgrId ? <span className="text-slate-500"> · </span> : null}
                  {reportMgrId ? (
                    <span className="font-mono text-slate-300">{reportMgrId}</span>
                  ) : reportMgrName ? null : (
                    "—"
                  )}
                </>
              ) : (
                <span className="text-slate-500">None — not set on your employee record.</span>
              )}
            </dd>
            {(leaderMgId || leaderName) && (
              <>
                <dt className="text-slate-500">People-leader roster</dt>
                <dd>
                  {leaderName ? <span>{leaderName}</span> : null}
                  {leaderName && leaderMgId ? <span className="text-slate-500"> · </span> : null}
                  {leaderMgId ? (
                    <span className="font-mono text-slate-300">{leaderMgId}</span>
                  ) : (
                    leaderName
                  )}
                  <span className="mt-1 block text-xs text-slate-500">
                    M-prefixed roster row linked to this employee record (separate from who you report to).
                  </span>
                </dd>
              </>
            )}
            <dt className="text-slate-500">Email</dt>
            <dd>{String(emp.email ?? "").trim() || "—"}</dd>
            <dt className="text-slate-500">Leave balance</dt>
            <dd>{summary.leave_balance}</dd>
          </dl>
          <h4 className="pt-2 font-medium text-slate-200">Leave requests</h4>
          <ul className="text-sm space-y-1">
            {summary.leave_requests.length === 0 && (
              <li className="text-slate-500">No leave requests yet.</li>
            )}
            {summary.leave_requests.map((r) => (
              <li key={String(r.leave_id)}>
                #{String(r.leave_id)} {String(r.start_date)} → {String(r.end_date)} —{" "}
                {String(r.status)}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tab === "team" && (
        <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
          <h3 className="font-semibold text-slate-50">Employees assigned to you</h3>
          <p className="text-sm text-slate-400">
            These people have <span className="font-mono text-slate-300">employees.manager_id</span> set to your
            employee id (<span className="font-mono text-slate-300">{String(emp.emp_id ?? "")}</span>) — they report to
            you in the HRMS org chart. HR can change assignments in Data → employees.
          </p>
          {directReports.length === 0 ? (
            <p className="rounded-lg border border-slate-700 bg-slate-950/50 p-4 text-sm text-slate-400">
              No employees are assigned to you yet. When HR sets another employee&apos;s reporting manager to your id,
              they will appear here.
            </p>
          ) : (
            <>
              <p className="text-sm text-slate-500">
                <span className="font-mono text-slate-300">{directReports.length}</span> direct report
                {directReports.length === 1 ? "" : "s"}
              </p>
              <div className="overflow-x-auto">
                <table className="w-full border-collapse border border-slate-700 text-sm">
                  <thead>
                    <tr className="bg-slate-800/90">
                      <th className="border p-2 text-left">Employee ID</th>
                      <th className="border p-2 text-left">Name</th>
                      <th className="border p-2 text-left">Email</th>
                    </tr>
                  </thead>
                  <tbody>
                    {directReports.map((r) => (
                      <tr key={r.emp_id}>
                        <td className="border p-2 font-mono text-slate-200">{r.emp_id}</td>
                        <td className="border p-2 text-slate-200">{r.name}</td>
                        <td className="border p-2 text-slate-400">{r.email || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {tab === "tickets" && (
        <div className="space-y-6 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
          <div>
            <h3 className="font-semibold text-slate-50">Raise a ticket</h3>
            <form onSubmit={submitTicket} className="mt-4 max-w-md space-y-3">
              <label className="block text-sm text-slate-300">
                Item / subject area
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                  value={ticketItem}
                  onChange={(e) => setTicketItem(e.target.value)}
                  placeholder="e.g. Laptop, VPN, Access"
                  required
                />
              </label>
              <label className="block text-sm text-slate-300">
                Reason / details
                <textarea
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                  value={ticketReason}
                  onChange={(e) => setTicketReason(e.target.value)}
                  placeholder="What do you need?"
                  rows={3}
                  required
                />
              </label>
              <label className="block text-sm text-slate-300">
                Title (optional)
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                  value={ticketTitle}
                  onChange={(e) => setTicketTitle(e.target.value)}
                  placeholder="Short summary for IT"
                />
              </label>
              <button
                type="submit"
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white"
              >
                Submit ticket
              </button>
            </form>
            {ticketMsg && (
              <p className="mt-3 text-sm text-slate-300" role="status">
                {ticketMsg}
              </p>
            )}
          </div>
          <div>
            <h3 className="font-semibold text-slate-50">Your tickets</h3>
            <ul className="mt-3 space-y-1 text-sm">
              {summary.tickets.length === 0 && <li className="text-slate-500">No tickets yet.</li>}
              {summary.tickets.map((t) => (
                <li key={t.ticket_id}>
                  <span className="font-mono text-slate-200">{t.ticket_id}</span> — {t.title || t.item} —{" "}
                  <span className="text-slate-400">{ticketStatusLabel(t.status)}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {tab === "meetings" && (
        <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
          <h3 className="font-semibold text-slate-50">Meetings</h3>
          <ul className="space-y-1 text-sm">
            {summary.meetings.length === 0 && <li className="text-slate-500">No meetings.</li>}
            {summary.meetings.map((m) => (
              <li key={m.meeting_id}>
                {m.date} — {m.topic || m.title}
              </li>
            ))}
          </ul>
        </div>
      )}

      {tab === "leave" && (
        <div className="space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
          <h3 className="font-semibold text-slate-50">Request leave</h3>
          <p className="text-sm text-slate-400">{summary.leave_history_text}</p>
          <form onSubmit={submitLeave} className="space-y-3 max-w-md">
            <label className="block text-sm">
              Start (YYYY-MM-DD)
              <input
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </label>
            <label className="block text-sm">
              End (YYYY-MM-DD)
              <input
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </label>
            <label className="block text-sm">
              Reason
              <input
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
              />
            </label>
            <label className="block text-sm">
              Message (optional)
              <textarea
                className="mt-1 w-full rounded border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={2}
              />
            </label>
            <button
              type="submit"
              className="rounded-lg bg-violet-600 px-4 py-2 text-white text-sm font-medium"
            >
              Submit request
            </button>
          </form>
          {leaveMsg && <p className="text-sm text-slate-300">{leaveMsg}</p>}
        </div>
      )}

      {tab === "chat" && <ChatPanel />}
    </div>
  );
}
