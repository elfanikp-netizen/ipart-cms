import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { errorText, getNetworkStatus } from "../api";
import type { NetworkStatus } from "../types";

interface NetworkStatusState {
  status: NetworkStatus | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<NetworkStatus | null>;
}

const NetworkStatusContext = createContext<NetworkStatusState | null>(null);

export function NetworkStatusProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<NetworkStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextStatus = await getNetworkStatus();
      setStatus(nextStatus);
      return nextStatus;
    } catch (err) {
      setError(errorText(err));
      setStatus(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 5 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  return (
    <NetworkStatusContext.Provider value={{ status, loading, error, refresh }}>
      {children}
    </NetworkStatusContext.Provider>
  );
}

export function useNetworkStatus() {
  const value = useContext(NetworkStatusContext);
  if (!value) throw new Error("useNetworkStatus must be used inside NetworkStatusProvider");
  return value;
}

export function NetworkStatusHeader() {
  const { status, loading, error, refresh } = useNetworkStatus();
  const vpnOn = status?.vpn_likely === true;
  const vpnOff = status?.vpn_likely === false;
  const label = loading && !status ? "CHECKING" : vpnOn ? "VPN ON" : vpnOff ? "VPN OFF" : "VPN UNKNOWN";

  return (
    <div className="vpn-header-status" title={error ?? status?.note ?? "VPN status is an estimate based on active adapter names."}>
      <span className={`vpn-indicator ${vpnOn ? "on" : vpnOff ? "off" : "unknown"}`} aria-live="polite">
        <span className="vpn-dot" aria-hidden="true" />
        {label}
      </span>
      <button
        type="button"
        className={`vpn-refresh${loading ? " spinning" : ""}`}
        onClick={() => void refresh()}
        disabled={loading}
        aria-label="Refresh VPN status"
        title="Refresh VPN status"
      >
        ↻
      </button>
    </div>
  );
}
