import { useEffect, useId, useRef, useState } from "react";
import { apiGet, apiPost } from "../api/client";

/** People-manager roster row (M id); reporting line uses linked_emp_id (E id) in HRMS. */
type ManagerRosterOption = {
  mgr_id: string;
  name: string;
  email: string | null;
  linked_emp_id: string;
};

type OnboardingResult = {
  hire_kind?: "employee" | "manager";
  new_employee_id: string;
  new_manager_id?: string;
  manager_id: string;
  reporting_manager_mgr_id?: string;
  welcome_email: string;
  manager_email_result: string;
  tickets: string[];
  meeting: string;
  meeting_datetime_used: string;
  portal_username?: string | null;
  portal_password?: string | null;
  portal_login_error?: string | null;
};

const STEPS = [
  { id: 1, label: "New hire" },
  { id: 2, label: "Manager" },
  { id: 3, label: "Confirm" },
  { id: 4, label: "Run" },
  { id: 5, label: "Done" },
] as const;

/** Atom company default — work addresses use first.last@atom.com from the hire's full name. */
const ATOM_EMAIL_DOMAIN = "atom.com";

function atomWorkEmailFromFullName(fullName: string): string {
  const words = fullName.trim().split(/\s+/).filter(Boolean);
  const sanitize = (raw: string) =>
    raw
      .normalize("NFD")
      .replace(/\p{M}/gu, "")
      .toLowerCase()
      .replace(/[^a-z0-9]/g, "");
  if (words.length === 0) return "";
  if (words.length === 1) {
    const local = sanitize(words[0]);
    return local ? `${local}@${ATOM_EMAIL_DOMAIN}` : "";
  }
  const first = sanitize(words[0]);
  const last = sanitize(words[words.length - 1]);
  if (!first && !last) return "";
  if (!last) return `${first}@${ATOM_EMAIL_DOMAIN}`;
  if (!first) return `${last}@${ATOM_EMAIL_DOMAIN}`;
  return `${first}.${last}@${ATOM_EMAIL_DOMAIN}`;
}

export function OnboardingWizard() {
  const uid = useId();
  const panelRef = useRef<HTMLElement>(null);
  const [step, setStep] = useState(1);
  const [employeeName, setEmployeeName] = useState("");
  const [employeeEmail, setEmployeeEmail] = useState("");
  /** When false, work email tracks full name as first.last@atom.com until the user edits it. */
  const [workEmailManual, setWorkEmailManual] = useState(false);
  const [isManagerHire, setIsManagerHire] = useState(false);
  const [managerName, setManagerName] = useState("");
  const [selectedManagerMgrId, setSelectedManagerMgrId] = useState("");
  const [managerOptions, setManagerOptions] = useState<ManagerRosterOption[]>([]);
  const [managerListLoading, setManagerListLoading] = useState(false);
  const [managerListError, setManagerListError] = useState<string | null>(null);
  const [portalPassword, setPortalPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<OnboardingResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const nameId = `${uid}-name`;
  const emailId = `${uid}-email`;
  const managerHireId = `${uid}-manager-hire`;
  const managerSelectId = `${uid}-manager`;
  const portalPwId = `${uid}-portal-pw`;

  useEffect(() => {
    const root = panelRef.current;
    if (!root) return;
    const focusable = root.querySelector<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    );
    focusable?.focus();
  }, [step]);

  useEffect(() => {
    if (step !== 2) return;
    let cancelled = false;
    setManagerListLoading(true);
    setManagerListError(null);
    (async () => {
      try {
        const data = await apiGet<{
          managers: ManagerRosterOption[];
        }>("/api/data/onboarding-managers");
        if (cancelled) return;
        const rows: ManagerRosterOption[] = (data.managers ?? []).map((m) => ({
          mgr_id: m.mgr_id,
          name: m.name,
          email: m.email ?? null,
          linked_emp_id: m.linked_emp_id,
        }));
        rows.sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
        setManagerOptions(rows);
      } catch (e) {
        if (!cancelled) {
          setManagerListError(e instanceof Error ? e.message : "Failed to load managers");
          setManagerOptions([]);
        }
      } finally {
        if (!cancelled) setManagerListLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [step]);

  async function runOnboarding() {
    setSubmitting(true);
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        employee_name: employeeName.trim(),
        is_manager_hire: isManagerHire,
      };
      if (workEmailManual) {
        payload.employee_email = employeeEmail.trim();
      }
      if (!isManagerHire) {
        payload.manager_mgr_id = selectedManagerMgrId.trim();
      }
      const pp = portalPassword.trim();
      if (pp.length >= 8) {
        payload.initial_portal_password = pp;
      }
      const data = await apiPost<OnboardingResult>("/api/onboarding/run", payload);
      setResult(data);
      setStep(5);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Onboarding failed");
    } finally {
      setSubmitting(false);
    }
  }

  const inputBase =
    "mt-1.5 w-full rounded-lg border border-slate-600/90 bg-slate-900/80 px-3 py-2.5 text-slate-100 placeholder:text-slate-500 shadow-inner " +
    "outline-none transition-[border-color,box-shadow,background-color] duration-200 " +
    "hover:border-slate-500 focus-visible:border-violet-400 focus-visible:ring-2 focus-visible:ring-violet-500/50 focus-visible:bg-slate-900";

  const btnPrimary =
    "inline-flex items-center justify-center rounded-lg bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm " +
    "transition-[background-color,transform,box-shadow] duration-200 " +
    "hover:bg-violet-500 active:scale-[0.98] " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 " +
    "disabled:pointer-events-none disabled:opacity-45";

  const btnSecondary =
    "inline-flex items-center justify-center rounded-lg border border-slate-600 bg-slate-800/60 px-4 py-2.5 text-sm font-medium text-slate-200 " +
    "transition-[background-color,border-color] duration-200 " +
    "hover:border-slate-500 hover:bg-slate-800 " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";

  const btnGhost =
    "text-sm font-medium text-violet-300 underline-offset-2 transition-colors hover:text-violet-200 " +
    "focus-visible:outline-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-violet-400 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950";

  return (
    <section
      ref={panelRef}
      aria-labelledby={`${uid}-title`}
      className="max-w-2xl mx-auto text-left"
    >
      <div className="rounded-2xl border border-slate-700/80 bg-slate-950 shadow-2xl shadow-black/50 ring-1 ring-white/5">
        <div className="border-b border-slate-800/90 px-5 py-4 sm:px-7 sm:py-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2
                id={`${uid}-title`}
                className="text-lg font-semibold tracking-tight text-slate-50 sm:text-xl"
              >
                Employee onboarding
              </h2>
            </div>
            <ol
              className="flex shrink-0 gap-1 rounded-lg bg-slate-900/80 p-1 ring-1 ring-slate-800"
              aria-label="Onboarding steps"
            >
              {STEPS.map((s) => {
                const active = step === s.id;
                const done = step > s.id;
                return (
                  <li
                    key={s.id}
                    aria-current={active ? "step" : undefined}
                    title={s.label}
                    className={
                      "flex h-8 min-w-[2rem] list-none items-center justify-center rounded-md px-2 text-xs font-medium transition-colors duration-200 " +
                      (active
                        ? "bg-violet-600 text-white shadow-sm"
                        : done
                          ? "text-slate-400"
                          : "text-slate-500")
                    }
                  >
                    {s.id}
                  </li>
                );
              })}
            </ol>
          </div>
        </div>

        <div className="px-5 py-6 sm:px-7 sm:py-8">
          <div key={step} className="onboarding-step-animate space-y-5">
            {step === 1 && (
              <div className="space-y-5">
                <div>
                  <label htmlFor={nameId} className="text-sm font-medium text-slate-300">
                    Full name
                  </label>
                  <input
                    id={nameId}
                    autoComplete="name"
                    className={inputBase}
                    value={employeeName}
                    onChange={(e) => {
                      const v = e.target.value;
                      setEmployeeName(v);
                      if (!workEmailManual) {
                        setEmployeeEmail(atomWorkEmailFromFullName(v));
                      }
                    }}
                    placeholder="Jane Doe"
                  />
                </div>
                <div>
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <label htmlFor={emailId} className="text-sm font-medium text-slate-300">
                      Work email
                    </label>
                    {workEmailManual && (
                      <button
                        type="button"
                        onClick={() => {
                          setWorkEmailManual(false);
                          setEmployeeEmail(atomWorkEmailFromFullName(employeeName));
                        }}
                        className="text-xs font-medium text-violet-400 underline-offset-2 hover:text-violet-300 hover:underline"
                      >
                        Use first.last@atom.com from name
                      </button>
                    )}
                  </div>
                  <input
                    id={emailId}
                    type="email"
                    autoComplete="email"
                    className={inputBase}
                    value={employeeEmail}
                    onChange={(e) => {
                      setWorkEmailManual(true);
                      setEmployeeEmail(e.target.value);
                    }}
                    placeholder={`jane.doe@${ATOM_EMAIL_DOMAIN}`}
                  />
                  <p className="mt-1 text-xs text-slate-500">
                    Auto-filled as <span className="font-mono text-slate-400">first.last@{ATOM_EMAIL_DOMAIN}</span>{" "}
                    from full name (Atom). Used as the employee portal{" "}
                    <span className="font-medium text-slate-400">username</span> when login is created.
                  </p>
                </div>
                <div>
                  <label htmlFor={portalPwId} className="text-sm font-medium text-slate-300">
                    Portal password <span className="font-normal text-slate-500">(optional)</span>
                  </label>
                  <input
                    id={portalPwId}
                    type="password"
                    autoComplete="new-password"
                    className={inputBase}
                    value={portalPassword}
                    onChange={(e) => setPortalPassword(e.target.value)}
                    placeholder="Leave blank to auto-generate (min 8 characters if you set one)"
                  />
                </div>
                <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-slate-700/90 bg-slate-900/40 px-3 py-3">
                  <input
                    id={managerHireId}
                    type="checkbox"
                    checked={isManagerHire}
                    onChange={(e) => {
                      setIsManagerHire(e.target.checked);
                      if (e.target.checked) {
                        setManagerName("");
                        setSelectedManagerMgrId("");
                        setManagerOptions([]);
                        setManagerListError(null);
                      }
                    }}
                    className="mt-1 h-4 w-4 shrink-0 rounded border-slate-600 text-violet-600 focus:ring-violet-500"
                  />
                  <span className="text-sm text-slate-300">
                    <span className="font-medium text-slate-100">People manager hire</span>
                    <span className="mt-0.5 block text-slate-400">
                      Creates both a manager roster entry and an employees record (laptop tickets, intro meeting,
                      leave). No reporting manager on file yet.
                    </span>
                  </span>
                </label>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    disabled={!employeeName.trim() || !employeeEmail.trim()}
                    onClick={() => setStep(isManagerHire ? 3 : 2)}
                    className={btnPrimary}
                  >
                    Continue
                  </button>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5">
                <div>
                  <label htmlFor={managerSelectId} className="text-sm font-medium text-slate-300">
                    Reporting manager
                  </label>
                  <select
                    id={managerSelectId}
                    className={
                      inputBase +
                      " mt-0 block w-full cursor-pointer appearance-none bg-[length:1rem] bg-[right_0.75rem_center] bg-no-repeat pr-10 " +
                      "[background-image:url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20fill%3D%22none%22%20viewBox%3D%220%200%2020%2020%22%3E%3Cpath%20stroke%3D%22%2394a3b8%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%20stroke-width%3D%221.5%22%20d%3D%22m6%208%204%204%204-4%22%2F%3E%3C%2Fsvg%3E')]"
                    }
                    value={selectedManagerMgrId}
                    disabled={managerListLoading}
                    onChange={(e) => {
                      const id = e.target.value;
                      setSelectedManagerMgrId(id);
                      const m = managerOptions.find((x) => x.mgr_id === id);
                      setManagerName(m?.name ?? "");
                    }}
                  >
                    <option value="">
                      {managerListLoading ? "Loading managers…" : "Choose a manager…"}
                    </option>
                    {managerOptions.map((m) => (
                      <option key={m.mgr_id} value={m.mgr_id}>
                        {m.name} — roster {m.mgr_id} (reports as employee {m.linked_emp_id})
                        {m.email ? ` — ${m.email}` : ""}
                      </option>
                    ))}
                  </select>
                </div>
                {managerListError && (
                  <p
                    className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200"
                    role="alert"
                  >
                    {managerListError}
                  </p>
                )}
                {!managerListLoading &&
                  !managerListError &&
                  managerOptions.length === 0 && (
                    <p className="text-sm text-amber-200/90">
                      No linked manager roster entries yet. Run a people-manager hire or add a manager row with a linked
                      employee ID (E…) so reporting lines can resolve to HRMS employees.
                    </p>
                  )}
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    disabled={!selectedManagerMgrId.trim() || !managerName.trim()}
                    onClick={() => setStep(3)}
                    className={btnPrimary}
                  >
                    Continue
                  </button>
                  <button type="button" onClick={() => setStep(1)} className={btnGhost}>
                    Back to new hire
                  </button>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-5">
                <dl className="grid gap-3 rounded-xl border border-slate-700/90 bg-slate-900/40 p-4 text-sm sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Hire type
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100">
                      {isManagerHire ? "Manager roster (managers table)" : "Employee (HRMS employees)"}
                    </dd>
                  </div>
                  <div className="sm:col-span-1">
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      New hire
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100">{employeeName}</dd>
                  </div>
                  <div className="sm:col-span-1">
                    <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                      Email
                    </dt>
                    <dd className="mt-1 font-medium text-slate-100 break-all">{employeeEmail}</dd>
                  </div>
                  {!isManagerHire && (
                    <>
                      <div className="sm:col-span-1">
                        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Manager roster ID
                        </dt>
                        <dd className="mt-1 font-mono text-sm font-medium text-slate-100">
                          {selectedManagerMgrId || "—"}
                        </dd>
                      </div>
                      <div className="sm:col-span-1">
                        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Linked employee (reporting line)
                        </dt>
                        <dd className="mt-1 font-mono text-sm font-medium text-slate-100">
                          {managerOptions.find((x) => x.mgr_id === selectedManagerMgrId)?.linked_emp_id ?? "—"}
                        </dd>
                      </div>
                      <div className="sm:col-span-2">
                        <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Manager name
                        </dt>
                        <dd className="mt-1 font-medium text-slate-100">{managerName}</dd>
                      </div>
                    </>
                  )}
                </dl>
                <div className="flex flex-wrap gap-2 pt-1">
                  <button
                    type="button"
                    onClick={() => setStep(isManagerHire ? 1 : 2)}
                    className={btnSecondary}
                  >
                    Back
                  </button>
                  <button type="button" onClick={() => setStep(4)} className={btnPrimary}>
                    Continue to run
                  </button>
                </div>
              </div>
            )}

            {step === 4 && (
              <div className="space-y-5">
                {error && (
                  <p
                    className="rounded-lg border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200"
                    role="alert"
                  >
                    {error}
                  </p>
                )}
                <div className="flex flex-wrap gap-2 pt-1">
                  <button type="button" onClick={() => setStep(3)} className={btnSecondary}>
                    Back
                  </button>
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => void runOnboarding()}
                    className={btnPrimary}
                  >
                    {submitting ? (
                      <span className="inline-flex items-center gap-2">
                        <span
                          className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"
                          aria-hidden
                        />
                        Running…
                      </span>
                    ) : (
                      "Run onboarding"
                    )}
                  </button>
                </div>
              </div>
            )}

            {step === 5 && result && (
              <div className="space-y-4">
                <p className="text-sm font-medium text-emerald-300">Onboarding completed</p>
                {result.portal_login_error ? (
                  <div
                    className="rounded-lg border border-amber-800/70 bg-amber-950/35 px-3 py-2 text-sm text-amber-100"
                    role="status"
                  >
                    <span className="font-medium text-amber-50">Portal login</span> could not be created:{" "}
                    {result.portal_login_error}
                  </div>
                ) : result.portal_username && result.portal_password ? (
                  <div
                    className="rounded-lg border border-violet-800/60 bg-violet-950/30 px-3 py-3 text-sm text-slate-200"
                    role="region"
                    aria-label="Employee portal login"
                  >
                    <p className="font-medium text-violet-200">Employee portal login</p>
                    <p className="mt-2 text-xs text-slate-400">
                      We do not email these credentials to the work address on file (it may be a placeholder). Share them
                      securely with the new hire. They sign in at the same HR-ASSIST app using the Employee role (not
                      HR).
                    </p>
                    <dl className="mt-3 space-y-2 font-mono text-xs sm:text-sm">
                      <div>
                        <dt className="text-slate-500">Username</dt>
                        <dd className="mt-0.5 break-all text-slate-100">{result.portal_username}</dd>
                      </div>
                      <div>
                        <dt className="text-slate-500">Temporary password</dt>
                        <dd className="mt-0.5 break-all text-slate-100">{result.portal_password}</dd>
                      </div>
                    </dl>
                  </div>
                ) : null}
                {result.hire_kind === "manager" && result.new_manager_id ? (
                  <p className="text-sm text-slate-300">
                    Manager roster ID:{" "}
                    <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs text-violet-200 ring-1 ring-slate-700">
                      {result.new_manager_id}
                    </code>
                  </p>
                ) : (
                  <div className="space-y-2 text-sm text-slate-300">
                    <p>
                      New employee ID:{" "}
                      <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs text-violet-200 ring-1 ring-slate-700">
                        {result.new_employee_id}
                      </code>
                    </p>
                    {!!result.reporting_manager_mgr_id?.trim() && (
                      <p>
                        Reporting manager:{" "}
                        <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs text-violet-200 ring-1 ring-slate-700">
                          {result.reporting_manager_mgr_id}
                        </code>
                      </p>
                    )}
                  </div>
                )}
                <p className="text-sm text-slate-400" role="status">
                  {result.welcome_email}
                </p>
                {!!result.manager_email_result?.trim() && (
                  <p className="text-sm text-slate-400">{result.manager_email_result}</p>
                )}
                {!!result.meeting?.trim() && (
                  <p className="text-sm text-slate-400">{result.meeting}</p>
                )}
                {result.tickets.length > 0 && (
                  <ul className="list-disc space-y-1 pl-5 font-mono text-xs text-slate-400 sm:text-sm">
                    {result.tickets.map((t) => (
                      <li key={t}>{t}</li>
                    ))}
                  </ul>
                )}
                <button
                  type="button"
                  onClick={() => {
                    setStep(1);
                    setResult(null);
                    setEmployeeName("");
                    setEmployeeEmail("");
                    setIsManagerHire(false);
                    setManagerName("");
                    setSelectedManagerMgrId("");
                    setManagerOptions([]);
                    setManagerListError(null);
                    setPortalPassword("");
                    setWorkEmailManual(false);
                    setError(null);
                  }}
                  className={btnGhost}
                >
                  Start another onboarding
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
