export type NodeType = "port" | "warehouse" | "hub";
export type EdgeMode = "sea" | "rail" | "truck" | "air";
export type Status = "normal" | "degraded" | "offline";
export type Priority = "standard" | "express" | "critical";
export type DisruptionSource = "manual" | "weather" | "news";
export type DisruptionTarget = "node" | "edge";

export interface Node {
  id: string;
  type: NodeType;
  lat: number;
  lon: number;
  name: string;
  country: string;
  capacity: number;
  current_load: number;
  status: Status;
}

export interface Edge {
  id: string;
  source_node_id: string;
  target_node_id: string;
  mode: EdgeMode;
  base_transit_mean_hours: number;
  base_transit_sigma: number;
  cost_per_unit: number;
  status: Status;
}

export interface Shipment {
  id: string;
  source_node_id: string;
  destination_node_id: string;
  path: string[];
  current_node_id: string;
  priority: Priority;
  sla_deadline: string;
  volume: number;
}

export interface Disruption {
  id: string;
  target_type: DisruptionTarget;
  target_id: string;
  severity: number;
  expected_duration_mean_hours: number;
  expected_duration_sigma_hours: number;
  source: DisruptionSource;
  created_at: string;
}

export interface ScenarioBucket {
  label: "optimistic" | "expected" | "pessimistic" | string;
  probability: number;
  eta: string;
}

export interface ETAForecast {
  shipment_id: string;
  p10: string;
  p50: string;
  p90: string;
  scenarios: ScenarioBucket[];
  cascade_impact_ids: string[];
}

export interface GraphSnapshot {
  nodes: Node[];
  edges: Edge[];
  shipments: Shipment[];
  disruptions: Disruption[];
}

export interface RerouteResult {
  shipment_id: string;
  new_path: string[];
  expected_transit_hours: number;
  expected_cost: number;
  original_path: string[];
}
