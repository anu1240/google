const WS_BASE = (import.meta.env.VITE_WS_BASE as string | undefined) ??
  "ws://localhost:8000";

export type LiveEvent =
  | { event: "disruption.added"; payload: any }
  | { event: "disruption.removed"; payload: { id: string } };

export function connectLive(
  onEvent: (ev: LiveEvent) => void
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;

  const open = () => {
    ws = new WebSocket(`${WS_BASE}/live`);
    ws.onmessage = (e) => {
      try { onEvent(JSON.parse(e.data) as LiveEvent); } catch {}
    };
    ws.onclose = () => {
      if (!closed) setTimeout(open, 2000);
    };
  };
  open();

  return () => {
    closed = true;
    ws?.close();
  };
}
