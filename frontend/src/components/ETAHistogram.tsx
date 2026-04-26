import { useMemo } from "react";
import type { ETAForecast } from "../types";

export function ETAHistogram({ forecast }: { forecast: ETAForecast }) {
  const { bars, labels } = useMemo(() => {
    const pts = [forecast.p10, forecast.p50, forecast.p90]
      .map((t) => new Date(t).getTime());
    const min = pts[0], max = pts[2];
    const buckets = 12;
    const width = (max - min) / buckets;
    const bars = new Array(buckets).fill(0);
    forecast.scenarios.forEach((s) => {
      const t = new Date(s.eta).getTime();
      const idx = Math.min(
        buckets - 1, Math.max(0, Math.floor((t - min) / width))
      );
      bars[idx] += s.probability;
    });
    const labels = [new Date(min), new Date(max)]
      .map((d) => d.toLocaleDateString(undefined, { month: "short", day: "numeric" }));
    return { bars, labels };
  }, [forecast]);

  const maxBar = Math.max(...bars, 0.01);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 60 }}>
        {bars.map((v, i) => (
          <div key={i} style={{
            flex: 1, background: "#3b82f6",
            height: `${(v / maxBar) * 100}%`, borderRadius: "2px 2px 0 0",
            minHeight: 2, opacity: 0.8,
          }} />
        ))}
      </div>
      <div style={{
        display: "flex", justifyContent: "space-between",
        fontSize: 10, color: "#64748b", marginTop: 4,
      }}>
        <span>{labels[0]}</span><span>{labels[1]}</span>
      </div>
    </div>
  );
}
