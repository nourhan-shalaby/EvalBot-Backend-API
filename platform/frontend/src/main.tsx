import { StrictMode, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "./components/Shell";
import { Spinner } from "./components/ui";
import "./index.css";
import { AuthProvider, useAuth } from "./lib/auth";
import { I18nProvider } from "./lib/i18n";
import Apply from "./pages/Apply";
import Auth from "./pages/Auth";
import Dashboard from "./pages/Dashboard";
import History from "./pages/History";
import InterviewRoom from "./pages/InterviewRoom";
import JobEditor from "./pages/JobEditor";
import JobDetail from "./pages/JobDetail";
import Jobs from "./pages/Jobs";
import Landing from "./pages/Landing";
import NewInterview from "./pages/NewInterview";
import Onboarding from "./pages/Onboarding";
import ReportPage from "./pages/Report";
import SettingsPage from "./pages/Settings";

// apply the saved theme before first paint
try {
  const s = localStorage.getItem("evalbot_theme");
  if (s === "dark" || (!s && window.matchMedia("(prefers-color-scheme: dark)").matches)) document.documentElement.classList.add("dark");
} catch {
  /* ignore */
}

function Private({ children, bare }: { children: ReactNode; bare?: boolean }) {
  const { ready, profile } = useAuth();
  const loc = useLocation();
  if (!ready) return <Spinner />;
  if (!profile) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return bare ? <>{children}</> : <AppShell>{children}</AppShell>;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <I18nProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Auth mode="signin" />} />
            <Route path="/signup" element={<Auth mode="signup" />} />
            <Route path="/apply/:token" element={<Apply />} />
            <Route path="/app/welcome" element={<Private bare><Onboarding /></Private>} />
            <Route path="/app" element={<Private><Dashboard /></Private>} />
            <Route path="/app/new" element={<Private><NewInterview /></Private>} />
            <Route path="/app/history" element={<Private><History /></Private>} />
            <Route path="/app/interview/:id" element={<Private bare><InterviewRoom /></Private>} />
            <Route path="/app/report/:id" element={<Private><ReportPage /></Private>} />
            <Route path="/app/settings" element={<Private><SettingsPage /></Private>} />
            <Route path="/app/jobs" element={<Private><Jobs /></Private>} />
            <Route path="/app/jobs/new" element={<Private><JobEditor /></Private>} />
            <Route path="/app/jobs/:id/edit" element={<Private><JobEditor /></Private>} />
            <Route path="/app/jobs/:id" element={<Private><JobDetail /></Private>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </I18nProvider>
  </StrictMode>,
);
