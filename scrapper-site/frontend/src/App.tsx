import { useEffect } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import DashboardPage from "./pages/DashboardPage";
import RunDetailPage from "./pages/RunDetailPage";
import ActivityPage from "./pages/ActivityPage";
import { NetworkStatusHeader, NetworkStatusProvider } from "./components/NetworkStatus";
import RunningVpnWarning from "./components/RunningVpnWarning";

function portalUrl(path = "") {
  const base = new URL(import.meta.env.VITE_PORTAL_BASE_URL ?? "/", window.location.origin);
  if (!base.pathname.endsWith("/")) base.pathname += "/";
  return new URL(path, base).toString();
}

function Shell() {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-session">Checking portal session...</div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <NetworkStatusProvider>
      <div className="container">
        <header className="topbar">
          <Link to="/" className="brand">Scraper CMS</Link>
          <nav className="menu">
            <Link to="/">Crawling</Link>
            <Link to="/activity">Activity</Link>
          </nav>
          <NetworkStatusHeader />
          <div className="user-chip">
            <span className={`badge ${user.role}`}>{user.role}</span>
            <span>{user.display_name || user.username}</span>
            <a className="small" href={portalUrl()}>Portal</a>
          </div>
        </header>
        <main>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/runs/:id" element={<RunDetailPage />} />
            <Route path="/activity" element={<ActivityPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
      <RunningVpnWarning />
    </NetworkStatusProvider>
  );
}

function PortalLoginRedirect() {
  useEffect(() => {
    window.location.replace(portalUrl("login"));
  }, []);
  return <div className="loading-session">Opening Portal Apps...</div>;
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<PortalLoginRedirect />} />
        <Route path="/*" element={<Shell />} />
      </Routes>
    </AuthProvider>
  );
}

