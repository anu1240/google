import { create } from "zustand";
import type {
  Node, Edge, Shipment, Disruption, ETAForecast,
} from "../types";
import { api } from "../api/client";

interface AppStore {
  nodes: Node[];
  edges: Edge[];
  shipments: Shipment[];
  disruptions: Disruption[];
  forecasts: Record<string, ETAForecast>;
  cascadeAffected: Set<string>;
  selectedShipmentId: string | null;
  loading: boolean;

  loadGraph: () => Promise<void>;
  runSimulation: () => Promise<void>;
  addDisruption: (d: Disruption) => void;
  removeDisruption: (id: string) => void;
  selectShipment: (id: string | null) => void;
}

export const useStore = create<AppStore>((set, get) => ({
  nodes: [],
  edges: [],
  shipments: [],
  disruptions: [],
  forecasts: {},
  cascadeAffected: new Set(),
  selectedShipmentId: null,
  loading: false,

  loadGraph: async () => {
    set({ loading: true });
    const g = await api.getGraph();
    set({
      nodes: g.nodes, edges: g.edges,
      shipments: g.shipments, disruptions: g.disruptions,
      loading: false,
    });
  },

  runSimulation: async () => {
    const { forecasts: prev } = get();
    const r = await api.simulate({ n: 500 });
    const next: Record<string, ETAForecast> = { ...prev };
    r.forecasts.forEach((f) => { next[f.shipment_id] = f; });
    set({ forecasts: next, cascadeAffected: new Set(r.cascade_affected) });
  },

  addDisruption: (d) => set((s) => ({
    disruptions: [...s.disruptions.filter((x) => x.id !== d.id), d],
  })),

  removeDisruption: (id) => set((s) => ({
    disruptions: s.disruptions.filter((x) => x.id !== id),
  })),

  selectShipment: (id) => set({ selectedShipmentId: id }),
}));
