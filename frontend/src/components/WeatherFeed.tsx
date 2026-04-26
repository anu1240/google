import { useStore } from "../state/store";
import { api } from "../api/client";
import { formatETA } from "../utils/format";

export function WeatherFeed() {
  const { disruptions, nodes } = useStore();
  const weatherDisruptions = disruptions.filter((d) => d.source === "weather");

  const nameFor = (id: string) =>
    nodes.find((n) => n.id === id)?.name ?? id;

  return (
    <div style={{ padding: 12, borderTop: "1px solid #e5e7eb" }}>
      <div style={{ fontSize: 11, color: "#0f766e", fontWeight: 600, marginBottom: 6 }}>
        Live weather triggers ({weatherDisruptions.length})
      </div>
      {weatherDisruptions.length === 0 ? (
        <div style={{ fontSize: 11, color: "#94a3b8" }}>No active weather disruptions.</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {weatherDisruptions.map((d) => (
            <div key={d.id} style={{
              padding: "6px 8px", border: "1px solid #e5e7eb",
              borderRadius: 4, fontSize: 11,
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ fontWeight: 600 }}>{nameFor(d.target_id)}</div>
                <div style={{ color: "#64748b" }}>
                  severity {d.severity.toFixed(2)} · started {formatETA(d.created_at)}
                </div>
              </div>
              <button onClick={() => api.deleteDisruption(d.id)}
                style={{
                  padding: "2px 8px", fontSize: 10,
                  background: "white", border: "1px solid #cbd5e1", borderRadius: 3,
                }}>
                Clear
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
