import React, { useState, useMemo } from "react";
import { api } from "../api";

export default function GridPreview({ project, onConfirmed }) {
  const rowCount = project.grid_rows;
  const colCount = project.grid_cols;

  const initialRowLabels = useMemo(() => {
    const arr = new Array(rowCount).fill("");
    project.grid_points.forEach((p) => { arr[p.row_index] = p.row_label; });
    return arr;
  }, [project]);

  const initialColLabels = useMemo(() => {
    const arr = new Array(colCount).fill("");
    project.grid_points.forEach((p) => { arr[p.col_index] = p.col_label; });
    return arr;
  }, [project]);

  const [rowLabels, setRowLabels] = useState(initialRowLabels);
  const [colLabels, setColLabels] = useState(initialColLabels);
  const [excludedIds, setExcludedIds] = useState(() => new Set());
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const xs = project.grid_points.map((p) => p.x_mm);
  const ys = project.grid_points.map((p) => p.y_mm);
  const xMin = Math.min(...xs), xMax = Math.max(...xs);
  const yMin = Math.min(...ys), yMax = Math.max(...ys);
  const span = (v, min, max) => (max === min ? 50 : ((v - min) / (max - min)) * 100);

  const toggleExcluded = (id) => {
    setExcludedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const activeCount = project.grid_points.length - excludedIds.size;

  const handleConfirm = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const points = project.grid_points
        .filter((p) => !excludedIds.has(p.id))
        .map((p) => ({
          id: p.id,
          row_label: rowLabels[p.row_index],
          col_label: colLabels[p.col_index],
        }));
      const updated = await api.confirmGrid(project.id, points, Array.from(excludedIds));
      onConfirmed(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="card">
      <div className="card-title">Review the generated grid</div>
      <div className="card-subtitle">
        {rowCount}×{colCount} bounding grid, {project.grid_pitch_x_mm}mm × {project.grid_pitch_y_mm}mm pitch.
        Rename the row/column axes to match your civil dept's convention. If the real survey is irregular —
        not every row/column intersection was actually measured — click a point below to exclude it.
      </div>

      <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
        <div style={{ flex: "0 0 auto" }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)" }}>Row labels</label>
          <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
            {rowLabels.map((val, i) => (
              <input
                key={i}
                value={val}
                onChange={(e) => {
                  const next = [...rowLabels];
                  next[i] = e.target.value;
                  setRowLabels(next);
                }}
                style={{
                  width: 56, padding: "5px 6px", fontFamily: "var(--font-mono)",
                  border: "1px solid var(--border-strong)", borderRadius: 4,
                }}
              />
            ))}
          </div>
        </div>

        <div style={{ flex: "0 0 auto" }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)" }}>Column labels</label>
          <div style={{ display: "flex", gap: 4, marginTop: 6, flexWrap: "wrap", maxWidth: 480 }}>
            {colLabels.map((val, i) => (
              <input
                key={i}
                value={val}
                onChange={(e) => {
                  const next = [...colLabels];
                  next[i] = e.target.value;
                  setColLabels(next);
                }}
                style={{
                  width: 56, padding: "5px 6px", fontFamily: "var(--font-mono)",
                  border: "1px solid var(--border-strong)", borderRadius: 4,
                }}
              />
            ))}
          </div>
        </div>
      </div>

      <div
        style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          marginTop: 18, marginBottom: 6,
        }}
      >
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--ink-soft)" }}>
          Click a point to include/exclude it
        </span>
        <span className="badge badge-neutral">
          {activeCount} of {project.grid_points.length} points active
        </span>
      </div>

      <div className="grid-paper" style={{ position: "relative", height: 360, padding: 20 }}>
        {project.grid_points.map((p) => {
          const excluded = excludedIds.has(p.id);
          return (
            <div
              key={p.id}
              onClick={() => toggleExcluded(p.id)}
              title={
                excluded
                  ? `Excluded — click to re-include (${p.x_mm}, ${p.y_mm}) mm`
                  : `${colLabels[p.col_index]}${rowLabels[p.row_index]} — (${p.x_mm}, ${p.y_mm}) mm — click to exclude`
              }
              style={{
                position: "absolute",
                left: `${span(p.x_mm, xMin, xMax)}%`,
                top: `${span(p.y_mm, yMin, yMax)}%`,
                transform: "translate(-50%, -50%)",
                width: 20, height: 20,
                display: "flex", alignItems: "center", justifyContent: "center",
                cursor: "pointer",
              }}
            >
              {excluded ? (
                <span style={{ fontSize: 13, lineHeight: 1, color: "var(--danger)", fontWeight: 700 }}>✕</span>
              ) : (
                <div style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--accent)" }} />
              )}
            </div>
          );
        })}
      </div>

      {error && <div className="error-banner" style={{ marginTop: 16 }}>{error}</div>}

      <div className="btn-row">
        <button className="btn btn-primary" onClick={handleConfirm} disabled={submitting}>
          {submitting ? "Confirming…" : `Confirm grid (${activeCount} points) & continue`}
        </button>
        {excludedIds.size > 0 && (
          <button type="button" className="btn" onClick={() => setExcludedIds(new Set())}>
            Reset exclusions
          </button>
        )}
      </div>
    </div>
  );
}
