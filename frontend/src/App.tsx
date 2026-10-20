import { Link, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import DashboardPage from "./pages/DashboardPage";
import RunDetailPage from "./pages/RunDetailPage";
import LoginPage from "./pages/LoginPage";
import AccountsPage from "./pages/AccountsPage";
import ActivityPage from "./pages/ActivityPage";
import ProfilePage from "./pages/ProfilePage";

function Shell() {
  const { user, logout } = useAuth();
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="container">
      <header className="topbar">
        <Link to="/" className="brand">🕷️ Scraper CMS</Link>
        <nav className="menu">
          <Link to="/">Crawling</Link>
          <Link to="/activity">Activity</Link>
          <Link to="/profile">Profile</Link>
          {user.role === "superadmin" && <Link to="/accounts">Accounts</Link>}
        </nav>
        <div className="user-chip">
          <span className={`badge ${user.role}`}>{user.role}</span>
          <span>{user.display_name || user.username}</span>
          <button className="small" onClick={logout}>Logout</button>
        </div>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/runs/:id" element={<RunDetailPage />} />
          <Route path="/activity" element={<ActivityPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route
            path="/accounts"
            element={user.role === "superadmin" ? <AccountsPage /> : <Navigate to="/" replace />}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/*" element={<Shell />} />
      </Routes>
    </AuthProvider>
  );
}

