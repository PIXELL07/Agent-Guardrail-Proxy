import { useEffect, useState, useCallback } from "react";
import { fetchStats, fetchAudit } from "./api";
import DetectionFunnel from "./components/DetectionFunnel";
import StatsCards from "./components/StatsCards";
import AuditTable from "./components/AuditTable";
import TryItPanel from "./components/TryItPanel";

const STORAGE_KEY_NOTE =
  "API key is kept only in memory for this session (not persisted) since browser storage isn't available here.";

function ApiKeyGate({ onSubmit }) {
  const [value, setValue] = useState("");

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg px-4">
      <div className="w-full max-w-sm bg-panel border border-border rounded-lg p-6">
        <h1 className="font-display font-semibold text-xl text-ink mb-1.5">
          Agent Guardrail Proxy
        </h1>
        <p className="text-sm text-muted mb-5">
          Enter an API key to view the audit dashboard.
        </p>
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && value && onSubmit(value)}
          placeholder="API key"
          className="w-full bg-bg border border-border rounded px-3 py-2 font-mono text-sm text-ink focus:outline-none focus:border-accent mb-3"
        />
        <button
          onClick={() => value && onSubmit(value)}
          className="w-full bg-accent text-bg font-display font-medium text-sm px-4 py-2 rounded hover:opacity-90 transition-opacity"
        >
          Connect
        </button>
        <p className="text-xs text-muted mt-4">{STORAGE_KEY_NOTE}</p>
      </div>
    </div>
  );
}

export default function App() {
  const [apiKey, setApiKey] = useState(null);
  const [stats, setStats] = useState(null);
  const [entries, setEntries] = useState([]);
  const [error, setError] = useState(null);

  const refresh = useCallback(async (key) => {
    try {
      const [statsData, auditData] = await Promise.all([
        fetchStats(key),
        fetchAudit(key, 50),
      ]);
      setStats(statsData);
      setEntries(auditData.entries);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    if (!apiKey) return;
    refresh(apiKey);
    const interval = setInterval(() => refresh(apiKey), 5000);
    return () => clearInterval(interval);
  }, [apiKey, refresh]);

  if (!apiKey) {
    return <ApiKeyGate onSubmit={setApiKey} />;
  }

  return (
    <div className="min-h-screen bg-bg font-body">
      <header className="border-b border-border px-6 py-5 flex items-center justify-between">
        <div>
          <h1 className="font-display font-semibold text-xl text-ink">
            Agent Guardrail Proxy
          </h1>
          <p className="text-xs text-muted mt-0.5">
            Live tool-call inspection · polling every 5s
          </p>
        </div>
        <button
          onClick={() => setApiKey(null)}
          className="text-xs text-muted hover:text-ink font-mono border border-border rounded px-3 py-1.5"
        >
          Disconnect
        </button>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8 flex flex-col gap-6">
        {error && (
          <div className="bg-block/10 border border-block rounded-lg px-4 py-3 text-sm text-block font-mono">
            {error}
          </div>
        )}

        <StatsCards stats={stats} />
        <DetectionFunnel stats={stats} />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <AuditTable entries={entries} />
          </div>
          <div>
            <TryItPanel apiKey={apiKey} onResult={() => refresh(apiKey)} />
          </div>
        </div>
      </main>
    </div>
  );
}
