import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { apiGet, apiPatch, apiPost, withDeadline } from "../api/client";
import { ChatPanel } from "./ChatPanel";
import { DataConsole } from "./DataConsole";
import { OnboardingWizard } from "./OnboardingWizard";

type Summary = {
  role: string;
  employee: Record<string, string> | null;
  pending_leave_requests: Array<Record<string, unknown>>;
  recent_tickets: Array<Record<string, string>>;
};

type Tab = "wizard" | "data" | "tickets" | "chat" | "queue";

const HR_TAB_IDS = new Set<Tab>(["wizard", "data", "tickets", "chat", "queue"]);

function normalizeHrTabParam(raw: string | undefined): Tab {
  if (raw && HR_TAB_IDS.has(raw as Tab)) return raw as Tab;
  return "wizard";
}

type QueueNotice = { kind: "ok" | "err"; text: string };

const PORTAL_SUMMARY_TIMEOUT_MS = 25_000;

function ticketStatusLabel(status: string): string {
  return status === "Closed" ? "Resolved" : status;
}

function isAbortError(e: unknown): boolean {
  return (
    (typeof DOMException !== "undefined" &&
      e instanceof DOMException &&
      e.name === "AbortError") ||
    (e instanceof Error && e.name === "AbortError")
  );
}

function summaryFetchErrorMessage(e: unknown): string {
  if (isAbortError(e)) {
    return (
      "Request timed out while loading workspace data. " +
      "Check that the API is running on port 8000 (or your configured URL). " +
      "If you use `npm run build` / preview, set VITE_API_BASE_URL or proxy /api to the API."
    );
  }
  if (e instanceof Error && /timed out after/i.test(e.message)) {
    return (
      `${e.message} ` +
      "Check that the API is running and reachable (Vite dev proxies /api to port 8000 by default)."
    );
  }
  return e instanceof Error ? e.message : "Failed to load summary";
}

function HrTicketListItem({
  t,
  variant,
  ticketActId,
  onSetStatus,
}: {
  t: Record<string, string>;
  variant: "active" | "history";
  ticketActId: string | null;
  onSetStatus: (ticketId: string, status: "Open" | "Closed") => void;
}) {
  const busy = ticketActId === t.ticket_id;
  const isClosed = t.status === "Closed";
  const isOpen = t.status === "Open";

  const btnNeutral =
    "rounded-md border px-2.5 py-1 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500/60 disabled:cursor-not-allowed disabled:opacity-45";
  const btnCurrent =
    "border-violet-500 bg-violet-950/40 text-violet-100 ring-1 ring-violet-500/40";
  const btnIdle = "border-slate-600 bg-slate-800/80 text-slate-200 hover:bg-slate-700";

  return (
    <li
      className={
        variant === "history"
          ? "border-b border-slate-800/80 pb-3 last:border-0 last:pb-0"
          : "border-b border-slate-800 pb-3 last:border-0 last:pb-0"
      }
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className={"min-w-0 flex-1 " + (variant === "history" ? "text-slate-400" : "")}>
          <div className={"font-mono " + (variant === "history" ? "text-slate-400" : "text-slate-200")}>
            {t.ticket_id}
          </div>
          <div className="mt-1">
            <span className="text-slate-500">Employee</span>{" "}
            <span className="font-mono text-slate-300">{t.emp_id}</span>
            {t.created_by && t.created_by === t.emp_id ? (
              <span className="text-slate-500"> · self-raised</span>
            ) : t.created_by ? (
              <span className="text-slate-500">
                {" "}
                · created by <span className="font-mono">{t.created_by}</span>
              </span>
            ) : null}
          </div>
          <div className="mt-1">
            {t.title || t.item} —{" "}
            <span className={variant === "history" ? "text-slate-500" : "text-slate-400"}>
              {ticketStatusLabel(t.status)}
            </span>
          </div>
          {t.reason ? (
            <p className="mt-1 line-clamp-2 text-xs text-slate-600">{t.reason}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:pt-0.5">
          {variant === "active" ? (
            <>
              <span className="text-xs text-slate-500 sm:sr-only">Set status</span>
              <button
                type="button"
                disabled={isOpen || busy}
                onClick={() => onSetStatus(t.ticket_id, "Open")}
                className={`${btnNeutral} ${isOpen ? btnCurrent : btnIdle}`}
              >
                Open
              </button>
              <button
                type="button"
                disabled={isClosed || busy}
                onClick={() => onSetStatus(t.ticket_id, "Closed")}
                className={`${btnNeutral} ${isClosed ? btnCurrent : btnIdle}`}
              >
                Resolved
              </button>
            </>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => onSetStatus(t.ticket_id, "Open")}
              className={`${btnNeutral} ${btnIdle}`}
            >
              Reopen
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

export function HrDashboard() {
  const { tab: tabParam } = useParams<{ tab: string }>();
  const navigate = useNavigate();
  const tab = normalizeHrTabParam(tabParam);

  useEffect(() => {
    if (tabParam !== tab) {
      navigate(`/app/hr/${tab}`, { replace: true });
    }
  }, [tabParam, tab, navigate]);

  const [summary, setSummary] = useState<Summary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [queueNotice, setQueueNotice] = useState<QueueNotice | null>(null);
  const [ticketNotice, setTicketNotice] = useState<QueueNotice | null>(null);
  const [ticketActId, setTicketActId] = useState<string | null>(null);
  const [actingOnId, setActingOnId] = useState<number | null>(null);
  const [ticketsRows, setTicketsRows] = useState<Array<Record<string, string>> | null>(null);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  const [ticketsErr, setTicketsErr] = useState<string | null>(null);

  const refreshTicketsTab = useCallback(async (signal?: AbortSignal) => {
    setTicketsLoading(true);
    setTicketsErr(null);
    try {
      const d = await withDeadline(
        apiGet<{ recent_tickets: Array<Record<string, string>> }>(
          "/api/portal/hr/recent-tickets",
          signal ? { signal } : undefined
        ),
        PORTAL_SUMMARY_TIMEOUT_MS,
        "Ticket list"
      );
      const list = d?.recent_tickets;
      if (!Array.isArray(list)) {
        setTicketsErr("Unexpected response from server.");
        setTicketsRows([]);
        return;
      }
      setTicketsRows(list);
    } catch (e) {
      if (isAbortError(e)) return;
      setTicketsErr(e instanceof Error ? e.message : "Failed to load tickets");
      setTicketsRows([]);
    } finally {
      setTicketsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (tab !== "tickets") return;
    const ac = new AbortController();
    void refreshTicketsTab(ac.signal);
    return () => ac.abort();
  }, [tab, refreshTicketsTab]);

  const refreshSummary = useCallback(async () => {
    const ctrl = new AbortController();
    try {
      const data = await withDeadline(
        apiGet<Summary>("/api/portal/summary", { signal: ctrl.signal }),
        PORTAL_SUMMARY_TIMEOUT_MS,
        "Workspace summary"
      );
      setSummary(data);
      setErr(null);
    } catch (e) {
      setErr(summaryFetchErrorMessage(e));
    }
  }, []);

  const retrySummary = useCallback(() => {
    const ctrl = new AbortController();
    setErr(null);
    setSummaryLoading(true);
    void (async () => {
      try {
        const data = await withDeadline(
          apiGet<Summary>("/api/portal/summary", { signal: ctrl.signal }),
          PORTAL_SUMMARY_TIMEOUT_MS,
          "Workspace summary"
        );
        setSummary(data);
        setErr(null);
      } catch (e) {
        setErr(summaryFetchErrorMessage(e));
      } finally {
        setSummaryLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    let alive = true;
    const ctrl = new AbortController();
    setSummaryLoading(true);
    void (async () => {
      try {
        const data = await withDeadline(
          apiGet<Summary>("/api/portal/summary", { signal: ctrl.signal }),
          PORTAL_SUMMARY_TIMEOUT_MS,
          "Workspace summary"
        );
        if (!alive) return;
        setSummary(data);
        setErr(null);
      } catch (e) {
        if (!alive) return;
        if (isAbortError(e)) return;
        setErr(summaryFetchErrorMessage(e));
      } finally {
        if (alive) setSummaryLoading(false);
      }
    })();
    return () => {
      alive = false;
      ctrl.abort();
    };
  }, []);

  const btn = (id: Tab, label: string) => (
    <button
      type="button"
      onClick={() => navigate(`/app/hr/${id}`)}
      aria-current={tab === id ? "page" : undefined}
      className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 ${
        tab === id
          ? "bg-violet-600 text-white shadow-sm"
          : "bg-slate-800 text-slate-300 hover:bg-slate-700"
      }`}
    >
      {label}
    </button>
  );

  async function approveLeave(requestId: number) {
    setQueueNotice(null);
    setActingOnId(requestId);
    try {
      const res = await apiPost<{ message: string }>(
        `/api/portal/leave/requests/${requestId}/approve`,
        {}
      );
      setQueueNotice({ kind: "ok", text: res.message });
      await refreshSummary();
    } catch (e) {
      setQueueNotice({
        kind: "err",
        text: e instanceof Error ? e.message : "Approve failed",
      });
    } finally {
      setActingOnId(null);
    }
  }

  async function rejectLeave(requestId: number) {
    setQueueNotice(null);
    setActingOnId(requestId);
    try {
      const res = await apiPost<{ message: string }>(
        `/api/portal/leave/requests/${requestId}/reject`,
        {}
      );
      setQueueNotice({ kind: "ok", text: res.message });
      await refreshSummary();
    } catch (e) {
      setQueueNotice({
        kind: "err",
        text: e instanceof Error ? e.message : "Reject failed",
      });
    } finally {
      setActingOnId(null);
    }
  }

  const pending = summary?.pending_leave_requests ?? [];
  const ticketsList = ticketsRows ?? [];
  const activeTicketsView = ticketsList.filter((t) => t.status !== "Closed");
  const historyTicketsView = ticketsList
    .filter((t) => t.status === "Closed")
    .sort((a, b) =>
      String(b.updated_at ?? "").localeCompare(String(a.updated_at ?? ""), undefined, {
        numeric: true,
      })
    );

  async function updateTicketStatus(ticketId: string, status: "Open" | "Closed") {
    setTicketNotice(null);
    setTicketActId(ticketId);
    try {
      await apiPatch<{ message: string }>(
        `/api/tickets/${encodeURIComponent(ticketId)}`,
        { status }
      );
      setTicketNotice({
        kind: "ok",
        text:
          status === "Closed"
            ? "Ticket resolved and moved to history."
            : "Ticket updated.",
      });
      await refreshSummary();
      await refreshTicketsTab();
    } catch (e) {
      setTicketNotice({
        kind: "err",
        text: e instanceof Error ? e.message : "Update failed",
      });
    } finally {
      setTicketActId(null);
    }
  }

  return (
    <div className="space-y-6">
      {err && (
        <p className="rounded-lg border border-amber-800/80 bg-amber-950/50 px-3 py-2 text-sm text-amber-100">
          {err}
        </p>
      )}
      {summary && pending.length > 0 && (
        <div className="rounded-lg border border-amber-800/80 bg-amber-950/40 px-4 py-3 text-sm text-amber-100">
          <strong>{pending.length}</strong> leave request(s) pending approval.
        </div>
      )}
      <nav
        className="flex flex-wrap gap-2"
        aria-label="HR workspace sections"
      >
        {btn("wizard", "Onboarding")}
        {btn("data", "Data")}
        {btn("tickets", "Tickets")}
        {btn("chat", "AI chat")}
        {btn("queue", "Leave queue")}
      </nav>
      {tab === "wizard" && (
        <div className="rounded-2xl bg-slate-900/40 p-3 ring-1 ring-slate-800/80 sm:p-4">
          <OnboardingWizard />
        </div>
      )}
      {tab === "data" && <DataConsole />}
      {tab === "tickets" && (
        <div className="rounded-xl border border-slate-700 bg-slate-900 p-6 text-left shadow-lg shadow-black/20">
          <h3 className="font-semibold text-slate-50">Tickets</h3>
          <p className="mt-1 text-sm text-slate-400">
            Active work below; resolving a ticket closes it and lists it under History in this tab.
          </p>
          {ticketNotice && (
            <p
              className={
                ticketNotice.kind === "ok"
                  ? "mt-3 rounded-lg border border-emerald-800/80 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-100"
                  : "mt-3 rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-100"
              }
            >
              {ticketNotice.text}
            </p>
          )}
          {ticketsLoading && <p className="mt-4 text-sm text-slate-400">Loading…</p>}
          {!ticketsLoading && ticketsErr && (
            <div className="mt-4 space-y-3">
              <p className="rounded-lg border border-amber-800/80 bg-amber-950/50 px-3 py-2 text-sm text-amber-100">
                {ticketsErr}
              </p>
              <button
                type="button"
                onClick={() => void refreshTicketsTab()}
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
              >
                Retry
              </button>
            </div>
          )}
          {!ticketsLoading && !ticketsErr && ticketsList.length === 0 ? (
            <p className="mt-4 text-sm text-slate-500">No tickets in the system.</p>
          ) : null}
          {!ticketsLoading && !ticketsErr && ticketsList.length > 0 ? (
            <div className="mt-6 space-y-8">
              <section aria-labelledby="tickets-active-heading">
                <h4 id="tickets-active-heading" className="text-sm font-semibold text-slate-200">
                  Active
                </h4>
                <p className="mt-0.5 text-xs text-slate-500">Open, in progress, or rejected — needs attention.</p>
                {activeTicketsView.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500">No active tickets.</p>
                ) : (
                  <ul className="mt-3 space-y-3 text-sm text-slate-300">
                    {activeTicketsView.map((t) => (
                      <HrTicketListItem
                        key={t.ticket_id}
                        t={t}
                        variant="active"
                        ticketActId={ticketActId}
                        onSetStatus={updateTicketStatus}
                      />
                    ))}
                  </ul>
                )}
              </section>
              <section aria-labelledby="tickets-history-heading">
                <h4 id="tickets-history-heading" className="text-sm font-semibold text-slate-200">
                  History
                </h4>
                <p className="mt-0.5 text-xs text-slate-500">Resolved (closed) tickets, newest first.</p>
                {historyTicketsView.length === 0 ? (
                  <p className="mt-3 text-sm text-slate-500">No resolved tickets yet.</p>
                ) : (
                  <ul className="mt-3 space-y-3 text-sm text-slate-300">
                    {historyTicketsView.map((t) => (
                      <HrTicketListItem
                        key={t.ticket_id}
                        t={t}
                        variant="history"
                        ticketActId={ticketActId}
                        onSetStatus={updateTicketStatus}
                      />
                    ))}
                  </ul>
                )}
              </section>
            </div>
          ) : null}
        </div>
      )}
      {tab === "chat" && <ChatPanel />}
      {tab === "queue" && (
        <div className="space-y-8 text-left">
          {summaryLoading && !summary && (
            <p className="text-sm text-slate-400">Loading…</p>
          )}
          {!summaryLoading && !summary && err && (
            <div className="rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
              <p className="text-sm text-slate-300">Could not load the leave queue.</p>
              <p className="mt-2 text-sm text-amber-100">{err}</p>
              <button
                type="button"
                onClick={retrySummary}
                className="mt-4 rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
              >
                Retry
              </button>
            </div>
          )}
          {summary && (
            <>
              {queueNotice && (
                <p
                  className={
                    queueNotice.kind === "ok"
                      ? "rounded-lg border border-emerald-900/50 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-200"
                      : "rounded-lg border border-red-900/60 bg-red-950/50 px-3 py-2 text-sm text-red-200"
                  }
                >
                  {queueNotice.text}
                </p>
              )}

              <div className="space-y-3 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/20">
                <h3 className="font-semibold text-slate-50">Pending leave requests</h3>
                {pending.length === 0 ? (
                  <p className="text-sm text-slate-500">No pending requests.</p>
                ) : (
                  <ul className="space-y-3 text-sm text-slate-300">
                    {pending.map((r) => {
                      const id = Number(r.leave_id);
                      const busy = actingOnId === id;
                      return (
                        <li
                          key={String(r.leave_id)}
                          className="flex flex-col gap-2 border-b border-slate-800 pb-3 last:border-0 sm:flex-row sm:items-center sm:justify-between"
                        >
                          <span>
                            <span className="font-mono text-slate-200">#{String(r.leave_id)}</span>{" "}
                            {typeof r.employee_name === "string" && r.employee_name.trim()
                              ? `${r.employee_name} (${String(r.employee_id)})`
                              : String(r.employee_id)}{" "}
                            — {String(r.start_date)} to {String(r.end_date)} — {String(r.reason)}
                          </span>
                          <div className="flex shrink-0 flex-wrap gap-2">
                            <button
                              type="button"
                              disabled={busy || Number.isNaN(id)}
                              onClick={() => void approveLeave(id)}
                              className="rounded-lg bg-emerald-700 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-600 disabled:opacity-50"
                            >
                              {busy ? "…" : "Approve"}
                            </button>
                            <button
                              type="button"
                              disabled={busy || Number.isNaN(id)}
                              onClick={() => void rejectLeave(id)}
                              className="rounded-lg border border-red-800/80 bg-red-950/40 px-3 py-1.5 text-xs font-medium text-red-200 hover:bg-red-950/60 disabled:opacity-50"
                            >
                              Reject
                            </button>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
