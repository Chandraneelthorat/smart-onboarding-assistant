import { useState } from "react";
import {
  apiPost,
  clearChatConversation,
  setAuthToken,
  type PortalSession,
} from "../api/client";

export type Session = PortalSession;

type Props = {
  onLoggedIn: (s: Session) => void;
};

export function LoginForm({ onLoggedIn }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data = await apiPost<{
        access_token: string;
        role: string;
        employee_id: string | null;
      }>("/api/auth/login", { email: email.trim(), password });
      setAuthToken(data.access_token);
      clearChatConversation();
      const rr = (data.role || "").trim().toLowerCase();
      const role: "hr" | "employee" = rr === "hr" ? "hr" : "employee";
      onLoggedIn({
        token: data.access_token,
        role,
        employeeId: data.employee_id,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      className="max-w-md mx-auto text-left space-y-4 rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-lg shadow-black/30"
    >
      <h2 className="text-lg font-semibold text-slate-50">Portal sign-in</h2>
      <label className="block text-sm font-medium text-slate-300">
        Email
        <input
          type="email"
          autoComplete="username"
          className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label className="block text-sm font-medium text-slate-300">
        Password
        <input
          type="password"
          autoComplete="current-password"
          className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-950 px-3 py-2 text-slate-100"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && <p className="text-sm text-red-300">{error}</p>}
      <button
        type="submit"
        disabled={loading}
        className="w-full rounded-lg bg-violet-600 py-2 font-medium text-white disabled:opacity-50"
      >
        {loading ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
