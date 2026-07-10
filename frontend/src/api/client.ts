const base =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") || "";

const TOKEN_KEY = "portal_token";

/** Persisted OpenRouter thread id (server returns on each /api/chat response). */
export const CHAT_CONVERSATION_KEY = "hr_assist_chat_conversation_id";

export function clearChatConversation(): void {
  sessionStorage.removeItem(CHAT_CONVERSATION_KEY);
}

export function setAuthToken(token: string | null): void {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export function getAuthToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

/** Mirrors login response; rebuilt on full page load from the stored JWT. */
export type PortalSession = {
  token: string;
  role: "hr" | "employee";
  employeeId: string | null;
};

function decodeJwtPayload(segment: string): Record<string, unknown> {
  let b64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const pad = b64.length % 4;
  if (pad) b64 += "=".repeat(4 - pad);
  const json = atob(b64);
  return JSON.parse(json) as Record<string, unknown>;
}

/**
 * Restore dashboard session after refresh. Uses the JWT payload only (no
 * extra round-trip); expired or malformed tokens are cleared.
 */
export function getPortalSessionFromStorage(): PortalSession | null {
  const token = getAuthToken();
  if (!token?.trim()) return null;
  const parts = token.split(".");
  if (parts.length !== 3) {
    setAuthToken(null);
    return null;
  }
  try {
    const payload = decodeJwtPayload(parts[1]);
    const exp = payload.exp;
    if (typeof exp === "number" && Date.now() / 1000 >= exp) {
      setAuthToken(null);
      return null;
    }
    const rawRole = String(payload.role ?? "").toLowerCase();
    const role: "hr" | "employee" = rawRole === "hr" ? "hr" : "employee";
    const emp = payload.emp_id;
    const employeeId =
      emp != null && String(emp).trim() !== "" ? String(emp).trim() : null;
    return { token, role, employeeId };
  } catch {
    setAuthToken(null);
    return null;
  }
}

function headers(): HeadersInit {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const key =
    import.meta.env.VITE_API_KEY || import.meta.env.VITE_HR_API_KEY;
  if (key) {
    h["X-API-Key"] = key;
  }
  const tok = getAuthToken();
  if (tok) {
    h["Authorization"] = `Bearer ${tok}`;
  }
  return h;
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const url = base ? `${base}${path}` : path;
  const res = await fetch(url, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err)
    );
  }
  return res.json() as Promise<T>;
}

export type ApiGetOptions = {
  /** Passed to `fetch`; use with `AbortController` or `AbortSignal.timeout(ms)`. */
  signal?: AbortSignal;
};

export async function apiGet<T>(path: string, opts?: ApiGetOptions): Promise<T> {
  const url = base ? `${base}${path}` : path;
  const res = await fetch(url, { headers: headers(), signal: opts?.signal });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err)
    );
  }
  return res.json() as Promise<T>;
}

/**
 * Ensures slow or stuck `fetch` calls cannot block UI forever: this promise
 * rejects after `ms` even if the underlying request never settles.
 */
export async function withDeadline<T>(
  promise: Promise<T>,
  ms: number,
  label = "Request"
): Promise<T> {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      promise,
      new Promise<never>((_, reject) => {
        timeoutId = setTimeout(() => {
          reject(new Error(`${label} timed out after ${ms} ms`));
        }, ms);
      }),
    ]);
  } finally {
    if (timeoutId !== undefined) clearTimeout(timeoutId);
  }
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const url = base ? `${base}${path}` : path;
  const res = await fetch(url, {
    method: "PATCH",
    headers: headers(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err)
    );
  }
  return res.json() as Promise<T>;
}

export async function apiDelete<T>(path: string): Promise<T> {
  const url = base ? `${base}${path}` : path;
  const res = await fetch(url, {
    method: "DELETE",
    headers: headers(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(
      typeof err.detail === "string" ? err.detail : JSON.stringify(err)
    );
  }
  return res.json() as Promise<T>;
}
