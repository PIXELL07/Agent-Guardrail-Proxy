const TIER_LABELS = {
  regex: "Regex",
  "similarity+classifier": "Similarity + Classifier",
  llm_judge: "LLM Judge",
};

const TIER_ORDER = ["regex", "similarity+classifier", "llm_judge"];

export default function DetectionFunnel({ stats }) {
  if (!stats) return null;

  const total = stats.total_inspections || 0;
  const funnel = stats.funnel_by_tier || {};

  let remaining = total;

  return (
    <div className="bg-panel border border-border rounded-lg p-6">
      <div className="flex items-baseline justify-between mb-6">
        <h2 className="font-display font-semibold text-lg text-ink">
          Detection funnel
        </h2>
        <span className="font-mono text-xs text-muted">
          {total} inspections total
        </span>
      </div>

      <div className="flex flex-col gap-0">
        {TIER_ORDER.map((tier, idx) => {
          const counts = funnel[tier] || { allow: 0, block: 0 };
          const resolvedHere = counts.allow + counts.block;
          const pctOfTotal = total ? (resolvedHere / total) * 100 : 0;
          const pctOfRemaining = remaining ? (resolvedHere / remaining) * 100 : 0;
          const isLast = idx === TIER_ORDER.length - 1;
          remaining -= resolvedHere;

          return (
            <div key={tier} className="relative">
              <div className="flex items-center gap-4 py-3">
                <div className="w-8 shrink-0 font-mono text-xs text-muted text-right">
                  {String(idx + 1).padStart(2, "0")}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-display text-sm font-medium text-ink">
                      {TIER_LABELS[tier]}
                    </span>
                    <span className="font-mono text-xs text-muted">
                      {resolvedHere} resolved · {pctOfTotal.toFixed(0)}% of traffic
                    </span>
                  </div>

                  {/* stacked bar: allow (teal) vs block (red) share of this tier */}
                  <div className="h-2 w-full rounded-full bg-panel2 overflow-hidden flex">
                    <div
                      className="h-full bg-allow transition-all duration-500"
                      style={{
                        width: resolvedHere
                          ? `${(counts.allow / resolvedHere) * 100}%`
                          : "0%",
                      }}
                    />
                    <div
                      className="h-full bg-block transition-all duration-500"
                      style={{
                        width: resolvedHere
                          ? `${(counts.block / resolvedHere) * 100}%`
                          : "0%",
                      }}
                    />
                  </div>
                </div>

                <div className="w-16 shrink-0 text-right">
                  <span className="font-mono text-xs text-muted">
                    {pctOfRemaining.toFixed(0)}%↓
                  </span>
                </div>
              </div>

              {!isLast && (
                <div className="ml-8 pl-4 border-l border-dashed border-border h-3" />
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-4 pt-4 border-t border-border flex items-center gap-6 text-xs font-mono">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-allow" />
          <span className="text-muted">allowed</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-block" />
          <span className="text-muted">blocked</span>
        </div>
        <div className="ml-auto text-muted">
          only <span className="text-judge">{stats.judge_call_count}</span> of{" "}
          {total} calls reached the judge model (
          {(stats.judge_call_rate * 100).toFixed(1)}%)
        </div>
      </div>
    </div>
  );
}
