import { createContext, useContext, useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { Link, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { createUser, deleteUser, errorText, fetchMe, listUsers, login as loginRequest, logout as logoutRequest, updateProfile, updateUser } from "./api";
import type { User } from "./api";

interface AuthState {
  user: User | null;
  loading: boolean;
  signIn: (username: string, password: string, remember: boolean) => Promise<void>;
  signOut: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthState | null>(null);
const SCRAPER_URL = import.meta.env.VITE_SCRAPER_URL ?? "/scrapper/";
const UNIVERSE_URL = import.meta.env.VITE_UNIVERSE_URL ?? "/universe/";

function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("Auth context is unavailable");
  return value;
}

function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMe().then(setUser).catch(() => setUser(null)).finally(() => setLoading(false));
  }, []);

  const signIn = async (username: string, password: string, remember: boolean) => {
    const currentUser = await loginRequest(username, password, remember);
    setUser(currentUser);
  };

  const signOut = async () => {
    try {
      await logoutRequest();
    } finally {
      setUser(null);
    }
  };

  return <AuthContext.Provider value={{ user, loading, signIn, signOut, setUser }}>{children}</AuthContext.Provider>;
}

function LoginPage() {
  const { signIn, user, loading } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (!loading && user) return <Navigate to="/" replace />;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await signIn(username, password, remember);
      navigate("/");
    } catch (reason) {
      setError(errorText(reason));
      setBusy(false);
    }
  };

  return (
    <main className="login-screen">
      <div className="login-art" aria-hidden="true"><div className="art-grid" /><span className="art-orbit orbit-one" /><span className="art-orbit orbit-two" /><div className="art-caption">PORTAL APPS <span>01 / 01</span></div></div>
      <section className="login-panel">
        <Link className="wordmark" to="/">PA<span>/</span></Link>
        <div className="login-copy"><p className="eyebrow">ONE ACCOUNT · ALL TOOLS</p><h1>Welcome to <br />iPart Portal.</h1><p>Sign in to reach your workspace.</p></div>
        <form className="portal-form" onSubmit={submit}>
          <label>Username<input autoFocus autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required /></label>
          <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <label className="remember"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} /><span>Stay signed in for 30 days</span></label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button className="primary-button" type="submit" disabled={busy}>{busy ? "Signing in..." : "Sign in"}<span aria-hidden="true">↗</span></button>
        </form>
        <p className="login-foot">Shared access for Portal Apps</p>
      </section>
    </main>
  );
}

function PortalShell() {
  const { user, loading, signOut } = useAuth();
  const location = useLocation();
  if (loading) return <div className="loading-screen">Checking session...</div>;
  if (!user) return <Navigate to="/login" state={{ from: location.pathname }} replace />;

  const doSignOut = async () => {
    await signOut();
  };

  return (
    <div className="portal-shell">
      <header className="portal-header">
        <Link to="/" className="wordmark">PA<span>/</span></Link>
        <nav className="header-nav" aria-label="Main navigation">
          <NavItem to="/" active={location.pathname === "/"}>Applications</NavItem>
          {user.role === "superadmin" && <NavItem to="/accounts" active={location.pathname === "/accounts"}>Accounts</NavItem>}
          <NavItem to="/profile" active={location.pathname === "/profile"}>Profile</NavItem>
        </nav>
        <div className="session-tools"><span className="session-user"><span className="avatar">{(user.display_name || user.username).slice(0, 1).toUpperCase()}</span><span>{user.display_name || user.username}</span></span><button className="quiet-button" onClick={doSignOut}>Sign out</button></div>
      </header>
      <main className="portal-main">
        <Routes>
          <Route path="/" element={<ApplicationsPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/accounts" element={user.role === "superadmin" ? <AccountsPage /> : <Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="portal-footer"><span>PORTAL APPS</span><span>Shared identity · {user.username}</span></footer>
    </div>
  );
}

function NavItem({ to, active, children }: { to: string; active: boolean; children: ReactNode }) {
  return <Link className={`nav-item${active ? " selected" : ""}`} to={to}>{children}</Link>;
}

function ApplicationsPage() {
  const { user } = useAuth();
  return (
    <section className="workspace-page">
      <div className="page-heading"><div><p className="eyebrow">YOUR WORKSPACE</p><h1>Applications</h1></div><span className="app-count">{(Number(Boolean(user?.app_access.scraper)) + Number(Boolean(user?.app_access.universe))).toString().padStart(2, "0")} <i>/ 02</i></span></div>
      <p className="page-intro">Choose a workspace to continue.</p>
      <div className="app-grid">
        {user?.app_access.scraper && <a className="app-tile" href={SCRAPER_URL}>
          <div className="tile-top"><span className="app-monogram">SC</span><span className="launch-mark" aria-label="Open application">↗</span></div>
          <div className="tile-bottom"><div><p className="eyebrow">DATA OPERATIONS</p><h2>Scraper CMS</h2><p>Run crawlers and manage extraction jobs.</p></div><span className="tile-arrow">Open workspace <b>→</b></span></div>
        </a>}
        {user?.app_access.universe && <a className="app-tile" href={UNIVERSE_URL}>
          <div className="tile-top"><span className="app-monogram">UN</span><span className="launch-mark" aria-label="Open application">↗</span></div>
          <div className="tile-bottom"><div><p className="eyebrow">MASTER DATA</p><h2>Universe CMS</h2><p>Maintain vehicle and VIN reference data.</p></div><span className="tile-arrow">Open workspace <b>→</b></span></div>
        </a>}
        <div className="app-placeholder"><span className="placeholder-plus">+</span><p>More applications<br />will appear here</p></div>
      </div>
      <div className="workspace-note"><span className="note-dot" /><p>Signed in as <strong>{user?.display_name || user?.username}</strong>. Your account is shared across applications.</p></div>
    </section>
  );
}

function ProfilePage() {
  const { user, setUser } = useAuth();
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (newPassword && newPassword !== confirmPassword) return setError("New password and confirmation do not match.");
    if (newPassword && !currentPassword) return setError("Enter your current password to set a new password.");
    setBusy(true);
    try {
      const updated = await updateProfile({ display_name: displayName, ...(newPassword ? { current_password: currentPassword, new_password: newPassword } : {}) });
      setUser(updated);
      setCurrentPassword(""); setNewPassword(""); setConfirmPassword("");
      setMessage("Profile updated.");
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="settings-page">
      <PageHeading eyebrow="ACCOUNT SETTINGS" title="My profile" detail="Manage your shared Portal Apps identity." />
      <form className="settings-form" onSubmit={submit}>
        <div className="settings-section"><div className="section-title"><span>01</span><div><h2>Personal details</h2><p>Visible across your workspaces.</p></div></div><div className="field-grid">
          <label>Username<input value={user?.username ?? ""} disabled /></label><label>Role<input value={user?.role ?? ""} disabled /></label><label className="wide-field">Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={100} /></label>
        </div></div>
        <div className="settings-section"><div className="section-title"><span>02</span><div><h2>Change password</h2><p>Use at least 8 characters for your new password.</p></div></div><div className="field-grid">
          <label className="wide-field">Current password<input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label><label>New password<input type="password" autoComplete="new-password" minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /></label><label>Confirm new password<input type="password" autoComplete="new-password" minLength={8} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
        </div></div>
        <div className="form-actions">{error && <p className="form-error" role="alert">{error}</p>}{message && <p className="form-success" role="status">{message}</p>}<button className="primary-button" disabled={busy}>{busy ? "Saving..." : "Save changes"}<span>↗</span></button></div>
      </form>
    </section>
  );
}

function PageHeading({ eyebrow, title, detail }: { eyebrow: string; title: string; detail: string }) {
  return <div className="page-heading settings-heading"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="page-intro">{detail}</p></div></div>;
}

function AccountsPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [query, setQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("user");
  const [appAccess, setAppAccess] = useState<User["app_access"]>({ scraper: true, universe: false });
  const [error, setError] = useState("");

  const refresh = () => listUsers().then(setUsers).catch((reason) => setError(errorText(reason)));
  useEffect(() => { refresh(); }, []);
  const filtered = users.filter((account) => `${account.username} ${account.display_name} ${account.role}`.toLowerCase().includes(query.toLowerCase()));

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setError("");
    try {
      await createUser({ username, password, display_name: displayName, role, app_access: appAccess });
      setUsername(""); setPassword(""); setDisplayName(""); setRole("user"); setAppAccess({ scraper: true, universe: false }); setShowForm(false); refresh();
    } catch (reason) { setError(errorText(reason)); }
  };

  const changeAccount = async (account: User, data: { role?: User["role"]; is_active?: boolean; app_access?: User["app_access"] }) => {
    try { await updateUser(account.id, data); refresh(); } catch (reason) { setError(errorText(reason)); }
  };

  const removeAccount = async (account: User) => {
    if (!window.confirm(`Delete account "${account.username}"?`)) return;
    try { await deleteUser(account.id); refresh(); } catch (reason) { setError(errorText(reason)); }
  };

  return (
    <section className="accounts-page">
      <div className="page-heading"><div><p className="eyebrow">GLOBAL ACCESS</p><h1>Accounts</h1><p className="page-intro">One directory for every application in this portal.</p></div><button className="primary-button" onClick={() => setShowForm((visible) => !visible)}>{showForm ? "Cancel" : "＋ New account"}</button></div>
      {showForm && <form className="create-account" onSubmit={submit}><label>Username<input value={username} onChange={(event) => setUsername(event.target.value)} required /></label><label>Password<input type="password" minLength={4} value={password} onChange={(event) => setPassword(event.target.value)} required /></label><label>Display name<input value={displayName} onChange={(event) => setDisplayName(event.target.value)} /></label><label>Role<select value={role} onChange={(event) => setRole(event.target.value)}><option value="user">User</option><option value="superadmin">Superadmin</option></select></label><fieldset className="app-access-fields"><legend>Application access</legend><label><input type="checkbox" checked={appAccess.scraper} onChange={(event) => setAppAccess((current) => ({ ...current, scraper: event.target.checked }))} />Scraper</label><label><input type="checkbox" checked={appAccess.universe} onChange={(event) => setAppAccess((current) => ({ ...current, universe: event.target.checked }))} />Universe</label></fieldset><button className="primary-button">Create account <span>↗</span></button></form>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="directory-toolbar"><span>{users.length} {users.length === 1 ? "account" : "accounts"}</span><label className="search-field"><span>⌕</span><input aria-label="Search accounts" placeholder="Search directory" value={query} onChange={(event) => setQuery(event.target.value)} /></label></div>
      <div className="directory-table-wrap"><table className="directory-table"><thead><tr><th>Account</th><th>Role</th><th>Status</th><th>Applications</th><th>Last sign in</th><th><span className="sr-only">Actions</span></th></tr></thead><tbody>
        {filtered.map((account) => <tr key={account.id}><td><div className="account-name"><span className="avatar">{(account.display_name || account.username).slice(0, 1).toUpperCase()}</span><div><strong>{account.display_name || account.username}</strong><small>@{account.username}</small></div></div></td><td><span className={`role-label ${account.role}`}>{account.role}</span></td><td><span className={`status-label ${account.is_active ? "active" : "inactive"}`}><i />{account.is_active ? "Active" : "Inactive"}</span></td><td><div className="account-app-access">{(["scraper", "universe"] as const).map((app) => <label key={app}><input type="checkbox" checked={Boolean(account.app_access?.[app])} onChange={(event) => changeAccount(account, { app_access: { ...(account.app_access ?? { scraper: false, universe: false }), [app]: event.target.checked } })} />{app === "scraper" ? "Scraper" : "Universe"}</label>)}</div></td><td className="last-seen">{account.last_login_at ? new Date(account.last_login_at).toLocaleString() : "Never"}</td><td><div className="row-actions"><button onClick={() => changeAccount(account, { is_active: !account.is_active })}>{account.is_active ? "Deactivate" : "Activate"}</button><button onClick={() => changeAccount(account, { role: account.role === "superadmin" ? "user" : "superadmin" })}>{account.role === "superadmin" ? "Make user" : "Make admin"}</button><button className="delete-action" onClick={() => removeAccount(account)}>Delete</button></div></td></tr>)}
        {filtered.length === 0 && <tr><td className="empty-table" colSpan={6}>No accounts match this search.</td></tr>}
      </tbody></table></div>
    </section>
  );
}

export default function App() {
  return <AuthProvider><Routes><Route path="/login" element={<LoginPage />} /><Route path="/*" element={<PortalShell />} /></Routes></AuthProvider>;
}