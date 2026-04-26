import type {
  GraphSnapshot, Disruption, DisruptionTarget, DisruptionSource,
  ETAForecast, RerouteResult,
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(
  path: string, init?: RequestInit
): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

export const api = {
  getGraph: () => request<GraphSnapshot>("/graph"),
  postDisruption: (body: {
    target_type: DisruptionTarget;
    target_id: string;
    severity: number;
    expected_duration_mean_hours: number;
    expected_duration_sigma_hours: number;
    source?: DisruptionSource;
  }) => request<Disruption>("/disruptions", {
    method: "POST", body: JSON.stringify(body),
  }),
  deleteDisruption: (id: string) => request<{ id: string; status: string }>(
    `/disruptions/${id}`, { method: "DELETE" }
  ),
  simulate: (body: { n?: number; shipment_ids?: string[] }) =>
    request<{ forecasts: ETAForecast[]; cascade_affected: string[] }>(
      "/simulate", { method: "POST", body: JSON.stringify(body) }
    ),
  reroute: (shipmentId: string) => request<RerouteResult>(
    `/reroute/${shipmentId}`, { method: "POST" }
  ),
};
