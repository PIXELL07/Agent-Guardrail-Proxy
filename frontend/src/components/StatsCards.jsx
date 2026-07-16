function StatCard({ label, value, accent }) {
  return (
    <div className="bg-panel border border-border rounded-lg px-5 py-4 flex-1 min-w-[160px]">
      <div className="text-xs text-muted font-body mb-1.5">{label}</div>
      <div
        className="font-display text-2xl font-semibold"
        style={{ color: accent || "#E7EDF0" }}
      >
        {value}
      </div>
    </div>
  );
}

export default function StatsCards({ stats }) {
  if (!stats) return null;

  return (
    <div className="flex flex-wrap gap-4">
      <StatCard label="Total inspections" value={stats.total_inspections} />
      <StatCard
        label="Blocked"
        value={`${stats.total_blocked} (${(stats.block_rate * 100).toFixed(1)}%)`}
        accent="#FF5C5C"
      />
      <StatCard
        label="Judge calls"
        value={`${stats.judge_call_count} (${(stats.judge_call_rate * 100).toFixed(1)}%)`}
        accent="#F2B84B"
      />
      <StatCard
        label="Avg latency"
        value={`${stats.avg_latency_ms.toFixed(1)} ms`}
        accent="#4FA8FF"
      />
    </div>
  );
}
