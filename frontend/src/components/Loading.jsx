import React from "react";

export default function Loading({ label = "Loading…" }) {
  return (
    <div className="card" style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <span className="spinner" aria-hidden="true" />
      <span style={{ color: "var(--ink-soft)", fontSize: 13 }}>{label}</span>
    </div>
  );
}
