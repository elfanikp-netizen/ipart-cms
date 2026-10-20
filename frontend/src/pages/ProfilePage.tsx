import { useEffect, useState } from "react";
import { errorText, getProfile, updateProfile } from "../api";
import { useAuth } from "../auth";

export default function ProfilePage() {
  const { user } = useAuth();
  const [displayName, setDisplayName] = useState(user?.display_name ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getProfile().then((profile) => setDisplayName(profile.display_name ?? "")).catch((e) => setError(errorText(e)));
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);

    if (newPassword && newPassword !== confirmPassword) {
      setError("New password and confirmation do not match.");
      return;
    }
    if (newPassword && !currentPassword) {
      setError("Enter your current password to set a new password.");
      return;
    }

    setBusy(true);
    try {
      const updated = await updateProfile({
        display_name: displayName,
        ...(newPassword ? { current_password: currentPassword, new_password: newPassword } : {}),
      });
      setDisplayName(updated.display_name ?? "");
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("Profile updated.");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card profile-card">
      <h1>My profile</h1>
      <form className="form" onSubmit={submit}>
        <label>
          Username
          <input value={user?.username ?? ""} disabled />
        </label>
        <label>
          Display name
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={100} />
        </label>
        <label>
          Account role
          <input value={user?.role ?? ""} disabled />
        </label>
        <div className="profile-divider" />
        <h2>Change password</h2>
        <label>
          Current password
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <label>
          New password
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            minLength={8}
            autoComplete="new-password"
          />
        </label>
        <label>
          Confirm new password
          <input
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={8}
            autoComplete="new-password"
          />
        </label>
        {error && <p className="error">{error}</p>}
        {message && <p className="success-message" role="status">{message}</p>}
        <button type="submit" disabled={busy}>{busy ? "Saving…" : "Save profile"}</button>
      </form>
    </section>
  );
}
