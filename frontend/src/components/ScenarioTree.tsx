import type { ScenarioBucket } from "../types";
import { formatETA } from "../utils/format";

const COLORS = {
  optimistic: "#16a34a",
  expected: "#2563eb",
  pessimistic: "#dc2626",
} as const;

export function ScenarioTree({ scenarios }: { scenarios: ScenarioBucket[] }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {scenarios.map((b) => {
        const color = (COLORS as any)[b.label] ?? "#64748b";
        const pct = Math.round(b.probability * 100);
        return (
          <div key={b.label} style={{
            display: "grid", gridTemplateColumns: "90px 1fr 140px",
            alignItems: "center", gap: 8, fontSize: 12,
          }}>
            <div style={{ color, fontWeight: 600, textTransform: "capitalize" }}>
              {b.label}
            </div>
            <div style={{ background: "#f1f5f9", height: 10, borderRadius: 5 }}>
              <div style={{
                background: color, height: "100%", width: `${pct}%`,
                borderRadius: 5, transition: "width 200ms",
              }} />
            </div>
            <div style={{ textAlign: "right", color: "#475569" }}>
              {pct}% · {formatETA(b.eta)}
            </div>
          </div>
        );
      })}
    </div>
  );
}
