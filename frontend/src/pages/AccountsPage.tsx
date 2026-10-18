import { useEffect, useState } from "react";
import type { User } from "../types";
import { createUser, deleteUser, errorText, listUsers, updateUser } from "../api";

export default function AccountsPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState("user");

  const load = () => listUsers().then(setUsers).catch((e) => setError(errorText(e)));
  useEffect(() => {
    load();
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    try {
      await createUser({ username, password, display_name: displayName, role });
      setUsername(""); setPassword(""); setDisplayName(""); setRole("user");
      setShowForm(false);
      load();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const toggleActive = async (u: User) => {
    try {
      await updateUser(u.id, { is_active: !u.is_active });
      load();
    } catch (e) {
      setError(errorText(e));
    }
  };

  const toggleRole = async (u: User) => {
    try {
      await updateUser(u.id, { role: u.role === "superadmin" ? "user" : "superadmin" });
      load();
    } catch (e) {
      setError(errorText(e));
    }
  };

  const remove = async (u: User) => {
    if (!confirm(`Delete account "${u.username}"?`)) return;
    try {
      await deleteUser(u.id);
      load();
    } catch (e) {
      setError(errorText(e));
    }
  };

  return (
    <section className="card">
      <div className="card-header">
        <h1>Accounts</h1>
        <button onClick={() => setShowForm((s) => !s)}>{showForm ? "Cancel" : "+ New account"}</button>
      </div>

      {showForm && (
        <form className="form inline-form" onSubmit={submit}>
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={4} />
          </label>
          <label>
            Display name
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="user">user</option>
              <option value="superadmin">superadmin</option>
            </select>
          </label>
          <button type="submit">Create</button>
        </form>
      )}

      {error && <p className="error">{error}</p>}

      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Username</th>
            <th>Display name</th>
            <th>Role</th>
            <th>Status</th>
            <th>Last login</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} className={u.is_active ? "" : "inactive"}>
              <td>{u.id}</td>
              <td>{u.username}</td>
              <td>{u.display_name || "-"}</td>
              <td>
                <span className={`badge ${u.role}`}>{u.role}</span>
              </td>
              <td>
                <span className={`badge ${u.is_active ? "active" : "disabled"}`}>
                  {u.is_active ? "active" : "inactive"}
                </span>
              </td>
              <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "never"}</td>
              <td className="actions">
                <button className="small" onClick={() => toggleActive(u)}>
                  {u.is_active ? "Deactivate" : "Activate"}
                </button>
                <button className="small" onClick={() => toggleRole(u)}>
                  {u.role === "superadmin" ? "Make user" : "Make admin"}
                </button>
                <button className="small danger" onClick={() => remove(u)}>Delete</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
