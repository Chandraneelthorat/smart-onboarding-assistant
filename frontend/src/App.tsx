import { Navigate, Outlet, Route, Routes, useNavigate } from "react-router-dom";
import { LoginForm } from "./components/LoginForm";
import { HrDashboard } from "./components/HrDashboard";
import { EmployeeDashboard } from "./components/EmployeeDashboard";
import { usePortalSession } from "./context/PortalSessionContext";

function RootRedirect() {
  const { session } = usePortalSession();
  if (!session) return <Navigate to="/login" replace />;
  return (
    <Navigate
      to={session.role === "hr" ? "/app/hr/wizard" : "/app/employee/overview"}
      replace
    />
  );
}

function LoginPage() {
  const { session, setSession } = usePortalSession();
  const navigate = useNavigate();

  if (session) {
    return (
      <Navigate
        to={session.role === "hr" ? "/app/hr/wizard" : "/app/employee/overview"}
        replace
      />
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-900/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-50">HR-ASSIST</h1>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <LoginForm
          onLoggedIn={(s) => {
            setSession(s);
            navigate(s.role === "hr" ? "/app/hr/wizard" : "/app/employee/overview", {
              replace: true,
            });
          }}
        />
      </main>
    </div>
  );
}

function AuthenticatedLayout() {
  const { session, logout } = usePortalSession();
  const navigate = useNavigate();

  if (!session) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-900/95 backdrop-blur-sm">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-slate-50">HR-ASSIST</h1>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-400">
              Signed in as <strong className="text-slate-200">{session.role}</strong>
              {session.employeeId ? ` · ${session.employeeId}` : ""}
            </span>
            <button
              type="button"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
              className="rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-slate-200 hover:bg-slate-800"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}

function AppHomeRedirect() {
  const { session } = usePortalSession();
  if (!session) return <Navigate to="/login" replace />;
  return (
    <Navigate
      to={session.role === "hr" ? "/app/hr/wizard" : "/app/employee/overview"}
      replace
    />
  );
}

function RequireHrRole({ children }: { children: React.ReactNode }) {
  const { session } = usePortalSession();
  if (session?.role !== "hr") {
    return <Navigate to="/app/employee/overview" replace />;
  }
  return children;
}

function RequireEmployeeRole({ children }: { children: React.ReactNode }) {
  const { session } = usePortalSession();
  if (session?.role !== "employee") {
    return <Navigate to="/app/hr/wizard" replace />;
  }
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/app" element={<AuthenticatedLayout />}>
        <Route index element={<AppHomeRedirect />} />
        <Route
          path="hr/:tab?"
          element={
            <RequireHrRole>
              <HrDashboard />
            </RequireHrRole>
          }
        />
        <Route
          path="employee/:tab?"
          element={
            <RequireEmployeeRole>
              <EmployeeDashboard />
            </RequireEmployeeRole>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
