import { useEffect, useState } from "react";
import { GraphView } from "./components/GraphView";
import { DisruptionModal } from "./components/DisruptionModal";
import { ShipmentPanel } from "./components/ShipmentPanel";
import { WeatherFeed } from "./components/WeatherFeed";
import { useStore } from "./state/store";
import { connectLive } from "./api/websocket";

export default function App() {
  const {
    loadGraph, runSimulation, addDisruption, removeDisruption,
    nodes, shipments, cascadeAffected, selectedShipmentId, selectShipment,
  } = useStore();
  const [injectNodeId, setInjectNodeId] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      await loadGraph();
      await runSimulation();
    })();
    const close = connectLive((ev) => {
      if (ev.event === "disruption.added") {
        addDisruption(ev.payload);
        runSimulation();
      } else if (ev.event === "disruption.removed") {
        removeDisruption(ev.payload.id);
        runSimulation();
      }
    });
    return close;
  }, [loadGraph, runSimulation, addDisruption, removeDisruption]);

  const injectNode = nodes.find((n) => n.id === injectNodeId);
  const selected = shipments.find((s) => s.id === selectedShipmentId);
  const cascadeShipments = shipments.filter((s) => cascadeAffected.has(s.id));

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", height: "100vh" }}>
      <GraphView onNodeClick={setInjectNodeId} />
      <aside style={{
        borderLeft: "1px solid #e5e7eb", overflow: "auto",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ padding: 12 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>Cascade Simulator</h2>
          <p style={{ fontSize: 11, color: "#64748b" }}>
            Click a node on the map to inject a disruption. Select a cascade-affected shipment to see its probabilistic ETA.
          </p>
        </div>

        <WeatherFeed />

        {cascadeShipments.length > 0 && (
          <div style={{ padding: 12, borderTop: "1px solid #e5e7eb" }}>
            <div style={{ fontSize: 11, color: "#991b1b", fontWeight: 600, marginBottom: 6 }}>
              {cascadeShipments.length} shipments affected
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 140, overflow: "auto" }}>
              {cascadeShipments.map((s) => (
                <button key={s.id} onClick={() => selectShipment(s.id)}
                  style={{
                    textAlign: "left", padding: "4px 8px",
                    border: "1px solid #e5e7eb", borderRadius: 4,
                    background: selectedShipmentId === s.id ? "#eff6ff" : "white",
                    fontSize: 11, cursor: "pointer",
                  }}>
                  {s.id} · {s.priority}
                </button>
              ))}
            </div>
          </div>
        )}

        {selected && <ShipmentPanel shipment={selected} />}
      </aside>
      <DisruptionModal
        nodeId={injectNodeId}
        nodeName={injectNode?.name ?? ""}
        onClose={() => setInjectNodeId(null)}
      />
    </div>
  );
}
