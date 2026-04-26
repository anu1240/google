import { useState } from "react";
import { api } from "../api/client";

export function DisruptionModal({
  nodeId, nodeName, onClose,
}: {
  nodeId: string | null;
  nodeName: string;
  onClose: () => void;
}) {
  const [severity, setSeverity] = useState(0.6);
  const [duration, setDuration] = useState(12);
  const [submitting, setSubmitting] = useState(false);

  if (!nodeId) return null;

  const submit = async () => {
    setSubmitting(true);
    try {
      await api.postDisruption({
        target_type: "node", target_id: nodeId,
        severity, expected_duration_mean_hours: duration,
        expected_duration_sigma_hours: duration * 0.25,
        source: "manual",
      });
      onClose();
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.4)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }} onClick={onClose}>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ background: "white", padding: 20, borderRadius: 8, minWidth: 320 }}
      >
        <h3 style={{ marginTop: 0 }}>Inject disruption at {nodeName}</h3>

        <label style={{ display: "block", marginTop: 12 }}>
          Severity: {severity.toFixed(2)}
          <input type="range" min={0} max={1} step={0.05}
            value={severity} onChange={(e) => setSeverity(+e.target.value)}
            style={{ display: "block", width: "100%" }} />
        </label>

        <label style={{ display: "block", marginTop: 12 }}>
          Expected duration (hours): {duration}
          <input type="range" min={1} max={72} step={1}
            value={duration} onChange={(e) => setDuration(+e.target.value)}
            style={{ display: "block", width: "100%" }} />
        </label>

        <div style={{ marginTop: 16, display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button onClick={onClose}>Cancel</button>
          <button onClick={submit} disabled={submitting}
            style={{ background: "#dc2626", color: "white", border: "none", padding: "6px 12px", borderRadius: 4 }}>
            {submitting ? "Injecting..." : "Inject"}
          </button>
        </div>
      </div>
    </div>
  );
}
