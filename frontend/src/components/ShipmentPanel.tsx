import { useState } from "react";
import type { Shipment } from "../types";
import { useStore } from "../state/store";
import { ScenarioTree } from "./ScenarioTree";
import { ETAHistogram } from "./ETAHistogram";
import { api } from "../api/client";
import { formatETA, formatHours } from "../utils/format";

export function ShipmentPanel({ shipment }: { shipment: Shipment }) {
  const forecast = useStore((s) => s.forecasts[shipment.id]);
  const cascadeAffected = useStore((s) => s.cascadeAffected.has(shipment.id));
  const nodes = useStore((s) => s.nodes);
  const nameFor = (id: string) =>
    nodes.find((n) => n.id === id)?.name ?? id;

  const [reroute, setReroute] = useState<any | null>(null);
  const [rerouting, setRerouting] = useState(false);

  const doReroute = async () => {
    setRerouting(true);
    try {
      const r = await api.reroute(shipment.id);
      setReroute(r);
    } catch (e: any) {
      alert(e.message);
    } finally {
      setRerouting(false);
    }
  };

  return (
    <div style={{ padding: 12, borderTop: "1px solid #e5e7eb" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <h3 style={{ margin: 0, fontSize: 14 }}>{shipment.id}</h3>
        {cascadeAffected && (
          <span style={{
            background: "#fee2e2", color: "#991b1b", fontSize: 10,
            padding: "2px 6px", borderRadius: 10,
          }}>CASCADE AFFECTED</span>
        )}
      </div>
      <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
        {nameFor(shipment.source_node_id)} → {nameFor(shipment.destination_node_id)} · {shipment.priority} · SLA {formatETA(shipment.sla_deadline)}
      </div>

      {forecast && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: "#475569", marginBottom: 6 }}>
            Delivery windows
          </div>
          <ScenarioTree scenarios={forecast.scenarios} />
          <div style={{ marginTop: 10 }}>
            <ETAHistogram forecast={forecast} />
          </div>
          <div style={{ fontSize: 10, color: "#64748b", marginTop: 6 }}>
            P10 {formatETA(forecast.p10)} · P50 {formatETA(forecast.p50)} · P90 {formatETA(forecast.p90)}
          </div>
        </div>
      )}

      <button onClick={doReroute} disabled={rerouting}
        style={{
          marginTop: 12, padding: "6px 12px", border: "none",
          background: "#2563eb", color: "white", borderRadius: 4,
        }}>
        {rerouting ? "Rerouting..." : "Recommend reroute"}
      </button>

      {reroute && (
        <div style={{ marginTop: 10, fontSize: 11, background: "#f0f9ff", padding: 8, borderRadius: 4 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>Recommended path</div>
          <div>{reroute.new_path.map(nameFor).join(" → ")}</div>
          <div style={{ marginTop: 4 }}>
            Transit: {formatHours(reroute.expected_transit_hours)} · Cost: {reroute.expected_cost.toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
}
