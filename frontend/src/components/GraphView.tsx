import { useMemo } from "react";
import ReactFlow, {
  Background, Controls, type Node as RFNode, type Edge as RFEdge,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";
import { useStore } from "../state/store";
import { projectLatLon } from "../utils/format";

interface GraphViewProps {
  onNodeClick?: (nodeId: string) => void;
}

export function GraphView({ onNodeClick }: GraphViewProps = {}) {
  const {
    nodes, edges, disruptions, cascadeAffected, shipments,
  } = useStore();

  const disruptedNodeIds = useMemo(
    () => new Set(
      disruptions.filter((d) => d.target_type === "node").map((d) => d.target_id)
    ),
    [disruptions]
  );

  const shipmentsOnEdge = useMemo(() => {
    const m = new Map<string, string[]>();
    shipments.forEach((s) => {
      for (let i = 0; i < s.path.length - 1; i++) {
        const k = `${s.path[i]}->${s.path[i + 1]}`;
        const arr = m.get(k) ?? [];
        arr.push(s.id);
        m.set(k, arr);
      }
    });
    return m;
  }, [shipments]);

  const cascadePathNodes = useMemo(() => {
    const ids = new Set<string>();
    shipments.forEach((s) => {
      if (cascadeAffected.has(s.id)) {
        const idx = s.path.indexOf(s.current_node_id);
        s.path.slice(idx >= 0 ? idx : 0).forEach((n) => ids.add(n));
      }
    });
    return ids;
  }, [shipments, cascadeAffected]);

  const rfNodes: RFNode[] = nodes.map((n) => {
    const { x, y } = projectLatLon(n.lat, n.lon);
    const disrupted = disruptedNodeIds.has(n.id);
    const onCascade = cascadePathNodes.has(n.id);
    const color = disrupted ? "#dc2626" : onCascade ? "#f97316" :
      n.type === "port" ? "#2563eb" :
      n.type === "hub" ? "#059669" : "#9333ea";
    return {
      id: n.id, position: { x, y },
      data: { label: `${n.type === "port" ? "🚢" : n.type === "hub" ? "🏭" : "📦"} ${n.name}` },
      style: {
        background: color, color: "white", borderRadius: 6,
        padding: "4px 8px", fontSize: 11, border: "none",
      },
    };
  });

  const rfEdges: RFEdge[] = edges.map((e) => {
    const key = `${e.source_node_id}->${e.target_node_id}`;
    const hasShipments = (shipmentsOnEdge.get(key)?.length ?? 0) > 0;
    const onCascade = cascadePathNodes.has(e.source_node_id) && cascadePathNodes.has(e.target_node_id);
    return {
      id: e.id, source: e.source_node_id, target: e.target_node_id,
      animated: hasShipments,
      style: {
        stroke: onCascade ? "#f97316" : "#94a3b8",
        strokeWidth: onCascade ? 2 : 1,
        opacity: hasShipments ? 0.9 : 0.35,
      },
      markerEnd: { type: MarkerType.ArrowClosed },
    };
  });

  return (
    <div style={{ height: "100%", width: "100%" }}>
      <ReactFlow
        nodes={rfNodes}
        edges={rfEdges}
        onNodeClick={(_e, n) => onNodeClick?.(n.id)}
        fitView
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
