import { useCallback, useEffect, useState } from "react";
import { apiDelete, apiGet, apiPatch } from "../api/client";

type View =
  | "employees"
  | "managers"
  | "leave_balances"
  | "tickets"
  | "email_logs";

const tabs: { id: View; label: string }[] = [
  { id: "employees", label: "employees" },
  { id: "managers", label: "managers" },
  { id: "leave_balances", label: "leave_balances" },
  { id: "tickets", label: "tickets" },
  { id: "email_logs", label: "email_logs" },
];

export function DataConsole() {
  const [view, setView] = useState<View>("employees");
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const clearFeedback = useCallback(() => {
    setErr(null);
    setMsg(null);
  }, []);

  return (
    <div className="mx-auto max-w-5xl space-y-6 text-left">
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => {
              setView(t.id);
              clearFeedback();
            }}
            className={`rounded-lg px-3 py-1.5 text-sm font-mono ${
              view === t.id
                ? "bg-violet-600 text-white"
                : "border border-slate-600 bg-slate-800 text-slate-300 hover:bg-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {err && (
        <p className="text-sm rounded border border-red-900/60 bg-red-950/50 p-2 text-red-200">{err}</p>
      )}
      {msg && (
        <p className="text-sm rounded border border-emerald-900/50 bg-emerald-950/40 p-2 text-emerald-200">
          {msg}
        </p>
      )}

      {view === "employees" && (
        <EmployeesPanel setErr={setErr} setMsg={setMsg} clearFeedback={clearFeedback} />
      )}
      {view === "managers" && (
        <ManagersPanel setErr={setErr} setMsg={setMsg} clearFeedback={clearFeedback} />
      )}
      {view === "leave_balances" && (
        <LeaveBalancesPanel setErr={setErr} setMsg={setMsg} clearFeedback={clearFeedback} />
      )}
      {view === "tickets" && (
        <TicketsPanel setErr={setErr} setMsg={setMsg} clearFeedback={clearFeedback} />
      )}
      {view === "email_logs" && (
        <EmailLogsPanel setErr={setErr} setMsg={setMsg} clearFeedback={clearFeedback} />
      )}
    </div>
  );
}

type Fb = {
  setErr: (s: string | null) => void;
  setMsg: (s: string | null) => void;
  clearFeedback: () => void;
};

function EmployeesPanel({ setErr, setMsg, clearFeedback }: Fb) {
  const [rows, setRows] = useState<
    { emp_id: string; name: string; manager_id: string | null; email: string | null }[]
  >([]);
  const [edit, setEdit] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [managerId, setManagerId] = useState("");

  const fetchEmployees = useCallback(async () => {
    try {
      const d = await apiGet<{ employees: typeof rows }>("/api/data/employees");
      const list = d?.employees;
      if (!Array.isArray(list)) {
        setErr("Unexpected response: expected a JSON object with an employees array.");
        setRows([]);
        return;
      }
      setErr(null);
      setRows(list);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    }
  }, [setErr]);

  const refreshEmployees = useCallback(() => {
    clearFeedback();
    return fetchEmployees();
  }, [clearFeedback, fetchEmployees]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void fetchEmployees();
    }, 0);
    return () => clearTimeout(id);
  }, [fetchEmployees]);

  async function save(empId: string) {
    clearFeedback();
    const n = name.trim();
    if (!n) {
      setErr("Name is required.");
      return;
    }
    try {
      await apiPatch(`/api/data/employees/${encodeURIComponent(empId)}`, {
        name: n,
        email: email.trim() ? email.trim() : null,
        manager_id: managerId.trim() ? managerId.trim() : null,
      });
      setMsg("Employee updated.");
      setEdit(null);
      await fetchEmployees();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function del(empId: string) {
    if (!confirm(`Delete employee ${empId} and related rows?`)) return;
    clearFeedback();
    try {
      await apiDelete(`/api/data/employees/${encodeURIComponent(empId)}`);
      setMsg("Deleted.");
      await fetchEmployees();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        HRMS employees (ids start with E). The reporting manager column must be another employee id (E…), not a
        manager roster id (M…).
      </p>
      <button
        type="button"
        onClick={() => void refreshEmployees()}
        className="text-sm text-violet-400"
      >
        Refresh
      </button>
      <div className="overflow-x-auto text-sm">
        <table className="w-full border-collapse border border-slate-700">
          <thead>
            <tr className="bg-slate-800/90">
              <th className="border p-2 text-left">emp_id</th>
              <th className="border p-2 text-left">name</th>
              <th className="border p-2 text-left">email</th>
              <th className="border p-2 text-left">manager_id</th>
              <th className="border p-2">actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td className="border p-4 text-slate-500" colSpan={5}>
                  No employees in this database yet. Add people via the Onboarding tab, or for local dev set{" "}
                  <code className="text-slate-300">HR_SEED_DEMO_EMPLOYEES=1</code> in <code className="text-slate-300">.env</code>{" "}
                  and restart the API once (creates demo E001/E002). Confirm the API is reachable on port 8000, then
                  Refresh.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.emp_id}>
                <td className="border p-2 font-mono">{r.emp_id}</td>
                <td className="border p-2">{r.name}</td>
                <td className="border p-2">{r.email ?? "—"}</td>
                <td className="border p-2">{r.manager_id ?? "—"}</td>
                <td className="border p-2 whitespace-nowrap">
                  <button
                    type="button"
                    className="text-violet-400 mr-2"
                    onClick={() => {
                      setEdit(r.emp_id);
                      setName(r.name);
                      setEmail(r.email ?? "");
                      setManagerId(r.manager_id ?? "");
                    }}
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    className="text-red-400"
                    onClick={() => del(r.emp_id)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4"
          role="presentation"
          onClick={() => setEdit(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="emp-edit-title"
            className="w-full max-w-md rounded-xl border border-slate-600 bg-slate-900 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="emp-edit-title" className="font-mono text-sm font-medium text-slate-100">
              Edit {edit}
            </h3>
            <div className="mt-4 space-y-3">
              <label className="block text-sm text-slate-300">
                Name
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Name"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Email (empty = none)
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Manager emp_id (empty = none)
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-100"
                  value={managerId}
                  onChange={(e) => setManagerId(e.target.value)}
                  placeholder="e.g. E001"
                />
              </label>
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
                onClick={() => save(edit)}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

type ManagerRow = {
  mgr_id: string;
  name: string;
  email: string | null;
  linked_emp_id: string | null;
  onboarding_status: string;
};

function ManagersPanel({ setErr, setMsg, clearFeedback }: Fb) {
  const [rows, setRows] = useState<ManagerRow[]>([]);
  const [edit, setEdit] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [linkedEmpId, setLinkedEmpId] = useState("");
  const [status, setStatus] = useState("Active");

  const fetchManagers = useCallback(async () => {
    try {
      const d = await apiGet<{ managers: ManagerRow[] }>("/api/data/managers");
      const list = d?.managers;
      if (!Array.isArray(list)) {
        setErr("Unexpected response: expected a JSON object with a managers array.");
        setRows([]);
        return;
      }
      setErr(null);
      setRows(list);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    }
  }, [setErr]);

  const refreshManagers = useCallback(() => {
    clearFeedback();
    return fetchManagers();
  }, [clearFeedback, fetchManagers]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void fetchManagers();
    }, 0);
    return () => clearTimeout(id);
  }, [fetchManagers]);

  async function save(mgrId: string) {
    clearFeedback();
    const n = name.trim();
    if (!n) {
      setErr("Name is required.");
      return;
    }
    try {
      await apiPatch(`/api/data/managers/${encodeURIComponent(mgrId)}`, {
        name: n,
        email: email.trim() ? email.trim() : null,
        linked_emp_id: linkedEmpId.trim() ? linkedEmpId.trim() : null,
        onboarding_status: status.trim() || "Active",
      });
      setMsg("Manager roster row updated.");
      setEdit(null);
      await fetchManagers();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
  }

  async function del(mgrId: string) {
    if (
      !confirm(
        `Delete manager roster row ${mgrId}? This does not delete the linked HRMS employee (if any).`
      )
    )
      return;
    clearFeedback();
    try {
      await apiDelete(`/api/data/managers/${encodeURIComponent(mgrId)}`);
      setMsg("Deleted.");
      await fetchManagers();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Delete failed");
    }
  }

  return (
    <div className="space-y-4">
      <p className="text-xs text-slate-500">
        People-manager roster (ids start with M). Optional linked_emp_id is the HRMS employee record (E…) used for
        tickets, leave, and portal. Onboarding reporting lines still resolve through this link.
      </p>
      <button type="button" onClick={() => void refreshManagers()} className="text-sm text-violet-400">
        Refresh
      </button>
      <div className="overflow-x-auto text-sm">
        <table className="w-full border-collapse border border-slate-700">
          <thead>
            <tr className="bg-slate-800/90">
              <th className="border p-2 text-left">mgr_id</th>
              <th className="border p-2 text-left">name</th>
              <th className="border p-2 text-left">email</th>
              <th className="border p-2 text-left">linked_emp_id</th>
              <th className="border p-2 text-left">onboarding_status</th>
              <th className="border p-2">actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr>
                <td className="border p-4 text-slate-500" colSpan={6}>
                  No manager roster rows. Create people-manager hires from Onboarding (manager hire) or add rows via
                  API; then Refresh.
                </td>
              </tr>
            )}
            {rows.map((r) => (
              <tr key={r.mgr_id}>
                <td className="border p-2 font-mono">{r.mgr_id}</td>
                <td className="border p-2">{r.name}</td>
                <td className="border p-2">{r.email ?? "—"}</td>
                <td className="border p-2 font-mono">{r.linked_emp_id ?? "—"}</td>
                <td className="border p-2">{r.onboarding_status}</td>
                <td className="border p-2 whitespace-nowrap">
                  <button
                    type="button"
                    className="mr-2 text-violet-400"
                    onClick={() => {
                      setEdit(r.mgr_id);
                      setName(r.name);
                      setEmail(r.email ?? "");
                      setLinkedEmpId(r.linked_emp_id ?? "");
                      setStatus(r.onboarding_status || "Active");
                    }}
                  >
                    Edit
                  </button>
                  <button type="button" className="text-red-400" onClick={() => del(r.mgr_id)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {edit && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 p-4"
          role="presentation"
          onClick={() => setEdit(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="mgr-edit-title"
            className="w-full max-w-md rounded-xl border border-slate-600 bg-slate-900 p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="mgr-edit-title" className="font-mono text-sm font-medium text-slate-100">
              Edit {edit}
            </h3>
            <div className="mt-4 space-y-3">
              <label className="block text-sm text-slate-300">
                Name
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Name"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Email (empty = none)
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Linked HRMS emp_id (empty = none)
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 font-mono text-sm text-slate-100"
                  value={linkedEmpId}
                  onChange={(e) => setLinkedEmpId(e.target.value)}
                  placeholder="e.g. E018"
                />
              </label>
              <label className="block text-sm text-slate-300">
                Onboarding status
                <input
                  className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-sm text-slate-100"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                  placeholder="Active"
                />
              </label>
            </div>
            <div className="mt-6 flex flex-wrap justify-end gap-2">
              <button
                type="button"
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 hover:bg-slate-800"
                onClick={() => setEdit(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500"
                onClick={() => save(edit)}
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function LeaveBalancesPanel({ setErr, setMsg, clearFeedback }: Fb) {
  const [rows, setRows] = useState<{ id: number; emp_id: string; balance: number }[]>([]);
  const [bal, setBal] = useState<Record<string, string>>({});

  const fetchLeaveBalances = useCallback(async () => {
    try {
      const d = await apiGet<{ leave_balances: typeof rows }>(
        "/api/data/leave-balances"
      );
      const list = d?.leave_balances;
      if (!Array.isArray(list)) {
        setErr("Unexpected response: expected leave_balances array.");
        setRows([]);
        setBal({});
        return;
      }
      setErr(null);
      setRows(list);
      const m: Record<string, string> = {};
      list.forEach((x) => {
        m[x.emp_id] = String(x.balance);
      });
      setBal(m);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    }
  }, [setErr]);

  const refreshLeaveBalances = useCallback(() => {
    clearFeedback();
    return fetchLeaveBalances();
  }, [clearFeedback, fetchLeaveBalances]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void fetchLeaveBalances();
    }, 0);
    return () => clearTimeout(id);
  }, [fetchLeaveBalances]);

  async function saveRow(empId: string) {
    clearFeedback();
    const n = parseInt(bal[empId] ?? "", 10);
    if (Number.isNaN(n) || n < 0) {
      setErr("Balance must be a non-negative integer.");
      return;
    }
    try {
      await apiPatch(`/api/data/leave-balances/${encodeURIComponent(empId)}`, {
        balance: n,
      });
      setMsg("Balance updated.");
      await fetchLeaveBalances();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
  }

  return (
    <div className="space-y-4">
      <button type="button" onClick={() => void refreshLeaveBalances()} className="text-sm text-violet-400">
        Refresh
      </button>
      <table className="w-full text-sm border-collapse border border-slate-700">
        <thead>
          <tr className="bg-slate-800/90">
            <th className="border p-2 text-left">emp_id</th>
            <th className="border p-2 text-left">balance</th>
            <th className="border p-2">save</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id}>
              <td className="border p-2 font-mono">{r.emp_id}</td>
              <td className="border p-2">
                <input
                  className="w-24 border rounded px-2 py-1 font-mono"
                  value={bal[r.emp_id] ?? ""}
                  onChange={(e) =>
                    setBal((b) => ({ ...b, [r.emp_id]: e.target.value }))
                  }
                />
              </td>
              <td className="border p-2">
                <button
                  type="button"
                  className="text-violet-400"
                  onClick={() => saveRow(r.emp_id)}
                >
                  Save
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TicketsPanel({ setErr, setMsg, clearFeedback }: Fb) {
  const [rows, setRows] = useState<
    {
      ticket_id: string;
      emp_id: string;
      item: string;
      reason: string;
      status: string;
      created_at: string;
      updated_at: string;
    }[]
  >([]);
  const [edit, setEdit] = useState<string | null>(null);
  const [item, setItem] = useState("");
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("Open");

  const fetchTickets = useCallback(async () => {
    try {
      const d = await apiGet<{ tickets: typeof rows }>("/api/data/tickets-all");
      const list = d?.tickets;
      if (!Array.isArray(list)) {
        setErr("Unexpected response: expected tickets array.");
        setRows([]);
        return;
      }
      setErr(null);
      setRows(list);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    }
  }, [setErr]);

  const refreshTickets = useCallback(() => {
    clearFeedback();
    return fetchTickets();
  }, [clearFeedback, fetchTickets]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void fetchTickets();
    }, 0);
    return () => clearTimeout(id);
  }, [fetchTickets]);

  async function save(ticketId: string) {
    clearFeedback();
    try {
      await apiPatch(`/api/data/tickets/${encodeURIComponent(ticketId)}/full`, {
        item: item.trim() || undefined,
        reason: reason.trim() || undefined,
        status: status as "Open" | "In Progress" | "Closed" | "Rejected",
      });
      setMsg("Ticket updated.");
      setEdit(null);
      await fetchTickets();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  async function del(ticketId: string) {
    if (!confirm(`Delete ticket ${ticketId}?`)) return;
    clearFeedback();
    try {
      await apiDelete(`/api/data/tickets/${encodeURIComponent(ticketId)}`);
      setMsg("Deleted.");
      await fetchTickets();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <div className="space-y-4">
      <button type="button" onClick={() => void refreshTickets()} className="text-sm text-violet-400">
        Refresh
      </button>
      <table className="w-full text-xs border-collapse border border-slate-700">
        <thead>
          <tr className="bg-slate-800/90">
            <th className="border p-1 text-left">ticket</th>
            <th className="border p-1 text-left">emp</th>
            <th className="border p-1 text-left">item</th>
            <th className="border p-1 text-left">status</th>
            <th className="border p-1"> </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticket_id}>
              <td className="border p-1 font-mono">{r.ticket_id}</td>
              <td className="border p-1 font-mono">{r.emp_id}</td>
              <td className="border p-1 max-w-[120px] truncate">{r.item}</td>
              <td className="border p-1">{r.status}</td>
              <td className="border p-1 whitespace-nowrap">
                <button
                  type="button"
                  className="text-violet-400 mr-1"
                  onClick={() => {
                    setEdit(r.ticket_id);
                    setItem(r.item);
                    setReason(r.reason);
                    setStatus(r.status);
                  }}
                >
                  Edit
                </button>
                <button
                  type="button"
                  className="text-red-400"
                  onClick={() => del(r.ticket_id)}
                >
                  Del
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {edit && (
        <div className="border rounded p-3 max-w-md space-y-2">
          <p className="font-mono text-sm">{edit}</p>
          <input
            className="w-full border rounded px-2 py-1 text-sm"
            value={item}
            onChange={(e) => setItem(e.target.value)}
            placeholder="item"
          />
          <textarea
            className="w-full border rounded px-2 py-1 text-sm"
            rows={2}
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
          <select
            className="w-full border rounded px-2 py-1 text-sm"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option>Open</option>
            <option>In Progress</option>
            <option>Closed</option>
            <option>Rejected</option>
          </select>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-violet-600 text-white px-3 py-1 text-sm"
              onClick={() => save(edit)}
            >
              Save
            </button>
            <button
              type="button"
              className="rounded border px-3 py-1 text-sm"
              onClick={() => setEdit(null)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function EmailLogsPanel({ setErr, setMsg, clearFeedback }: Fb) {
  const [rows, setRows] = useState<
    {
      id: number;
      emp_id: string | null;
      to_addresses: string;
      subject: string;
      body: string;
      is_html: boolean;
      purpose: string | null;
      delivery_status: string;
      error_detail: string | null;
      created_at: string | null;
    }[]
  >([]);
  const [total, setTotal] = useState(0);
  const [empFilter, setEmpFilter] = useState("");

  const fetchEmailLogs = useCallback(async () => {
    try {
      const q = empFilter.trim()
        ? `?emp_id=${encodeURIComponent(empFilter.trim())}&limit=100`
        : "?limit=100";
      const d = await apiGet<{ total: number; email_logs: typeof rows }>(
        `/api/data/email-logs${q}`
      );
      const list = d?.email_logs;
      if (!Array.isArray(list)) {
        setErr("Unexpected response: expected email_logs array.");
        setRows([]);
        setTotal(0);
        return;
      }
      setErr(null);
      setRows(list);
      setTotal(typeof d?.total === "number" ? d.total : list.length);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Load failed");
    }
  }, [empFilter, setErr]);

  const refreshEmailLogs = useCallback(() => {
    clearFeedback();
    return fetchEmailLogs();
  }, [clearFeedback, fetchEmailLogs]);

  async function del(id: number) {
    if (!confirm("Delete this email log row?")) return;
    clearFeedback();
    try {
      await apiDelete(`/api/data/email-logs/${id}`);
      setMsg("Deleted.");
      await fetchEmailLogs();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap items-end">
        <label className="text-sm">
          Filter emp_id
          <input
            className="block border rounded px-2 py-1 mt-1 font-mono"
            value={empFilter}
            onChange={(e) => setEmpFilter(e.target.value)}
          />
        </label>
        <button type="button" onClick={() => void refreshEmailLogs()} className="rounded border px-3 py-1 text-sm">
          Load
        </button>
        <span className="text-sm text-slate-500">total matching: {total}</span>
      </div>
      <div className="space-y-3">
        {rows.map((r) => (
          <div
            key={r.id}
            className="border border-slate-700 rounded-lg p-3 bg-slate-900 text-sm"
          >
            <div className="flex justify-between gap-2 flex-wrap">
              <span className="font-mono text-xs">
                #{r.id} · {r.delivery_status} · {r.created_at}
              </span>
              <button
                type="button"
                className="text-red-400 text-xs"
                onClick={() => del(r.id)}
              >
                Delete
              </button>
            </div>
            <p className="text-slate-400 text-xs mt-1">
              To: {r.to_addresses} · emp_id: {r.emp_id ?? "—"}
            </p>
            <p className="font-medium">{r.subject}</p>
            <pre className="text-xs whitespace-pre-wrap bg-slate-800/90 p-2 rounded mt-1 max-h-40 overflow-auto">
              {r.body.length > 800 ? `${r.body.slice(0, 800)}…` : r.body}
            </pre>
            {r.error_detail && (
              <p className="mt-1 text-xs text-red-300">{r.error_detail}</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
