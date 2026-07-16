import { useState } from "react";

const TIER_COLORS = {
  regex: "#FF5C5C",
  "similarity+classifier": "#F2B84B",
  llm_judge: "#4FA8FF",
};

function DecisionBadge({ decision }) {
  const isBlock = decision === "block";
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-mono font-medium"
      style={{
        backgroundColor: isBlock ? "#FF5C5C1A" : "#2FD6B31A",
        color: isBlock ? "#FF5C5C" : "#2FD6B3",
      }}
    >
      <span
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: isBlock ? "#FF5C5C" : "#2FD6B3" }}
      />
      {decision}
    </span>
  );
}

function TierBadge({ tier }) {
  const color = TIER_COLORS[tier] || "#7E8C94";
  return (
    <span
      className="px-2 py-0.5 rounded text-xs font-mono"
      style={{ backgroundColor: `${color}1A`, color }}
    >
      {tier}
    </span>
  );
}

function AuditRow({ entry }) {
  const [expanded, setExpanded] = useState(false);
  const tierResults = JSON.parse(entry.tier_results_json || "[]");
  const args = JSON.parse(entry.arguments_json || "{}");
  const time = new Date(entry.ts * 1000).toLocaleTimeString();

  return (
    <>
      <tr
        className="border-b border-border hover:bg-panel2 cursor-pointer transition-colors"
        onClick={() => setExpanded((e) => !e)}
      >
        <td className="py-2.5 px-4 font-mono text-xs text-muted whitespace-nowrap">
          {time}
        </td>
        <td className="py-2.5 px-4 font-mono text-xs text-ink whitespace-nowrap">
          {entry.agent_id}
        </td>
        <td className="py-2.5 px-4 font-mono text-xs text-ink whitespace-nowrap">
          {entry.tool_name}
        </td>
        <td className="py-2.5 px-4">
          <DecisionBadge decision={entry.decision} />
        </td>
        <td className="py-2.5 px-4">
          <TierBadge tier={entry.resolved_tier} />
        </td>
        <td className="py-2.5 px-4 font-mono text-xs text-muted whitespace-nowrap">
          {entry.latency_ms.toFixed(1)} ms
        </td>
        <td className="py-2.5 px-4 text-xs text-muted truncate max-w-[280px]">
          {entry.reason}
        </td>
      </tr>
      {expanded && (
        <tr className="border-b border-border bg-panel2">
          <td colSpan={7} className="px-4 py-4">
            <div className="grid grid-cols-2 gap-6">
              <div>
                <div className="text-xs text-muted mb-2 font-body">Arguments inspected</div>
                <pre className="font-mono text-xs text-ink bg-bg rounded p-3 overflow-x-auto border border-border">
                  {JSON.stringify(args, null, 2)}
                </pre>
              </div>
              <div>
                <div className="text-xs text-muted mb-2 font-body">Per-tier results</div>
                <div className="flex flex-col gap-2">
                  {tierResults.map((tr, i) => (
                    <div
                      key={i}
                      className="bg-bg border border-border rounded p-2.5 flex items-start gap-2"
                    >
                      <TierBadge tier={tr.tier} />
                      <div className="flex-1 min-w-0">
                        <div className="text-xs text-ink">{tr.reason}</div>
                        <div className="text-xs text-muted font-mono mt-0.5">
                          triggered: {String(tr.triggered)} · confidence: {tr.confidence.toFixed(2)}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function AuditTable({ entries }) {
  return (
    <div className="bg-panel border border-border rounded-lg overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <h2 className="font-display font-semibold text-lg text-ink">Recent inspections</h2>
        <span className="text-xs text-muted font-mono">click a row to expand</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-xs text-muted font-body border-b border-border">
              <th className="py-2.5 px-4 font-medium">Time</th>
              <th className="py-2.5 px-4 font-medium">Agent</th>
              <th className="py-2.5 px-4 font-medium">Tool</th>
              <th className="py-2.5 px-4 font-medium">Decision</th>
              <th className="py-2.5 px-4 font-medium">Resolved at</th>
              <th className="py-2.5 px-4 font-medium">Latency</th>
              <th className="py-2.5 px-4 font-medium">Reason</th>
            </tr>
          </thead>
          <tbody>
            {entries.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-muted text-sm">
                  No inspections yet. Send a tool call through /v1/inspect to see it here.
                </td>
              </tr>
            ) : (
              entries.map((entry) => <AuditRow key={entry.id} entry={entry} />)
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
