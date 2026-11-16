import React, { useEffect, useState } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";
import { api } from "../api";
import Loading from "./Loading";
import {
  DEFAULT_TIERS_4, DEFAULT_TIERS_3, classify, buildRiskColorscale,
  tierRangeText, addWorstTier, removeTier,
} from "../lib/riskTiers";

const Plot = createPlotlyComponent(Plotly);

function TierRow({ tier, index, isLast, onChange, onRemove, canRemove }) {
  // Same local-text-state pattern as the original 3-tier panel: show exactly
  // what's typed (including a bare "-") and only commit once it parses to a
  // real number, so typing a negative boundary never gets clobbered mid-keystroke.
  const [text, setText] = useState(tier.boundary === null ? "" : String(tier.boundary));

  useEffect(() => {
    setText(tier.boundary === null ? "" : String(tier.boundary));
  }, [tier.boundary]);

  const handleBoundaryChange = (raw) => {
    setText(raw);
    if (raw === "" || raw === "-") return;
    const n = Number(raw);
    if (Number.isFinite(n)) onChange({ ...tier, boundary: n });
  };

  return (
    <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "6px 0" }}>
      <input
        type="color"
        value={tier.color}
        onChange={(e) => onChange({ ...tier, color: e.target.value })}
        style={{ width: 30, height: 26, padding: 0, border: "1px solid var(--border-strong)", borderRadius: 4 }}
      />
      <input
        type="text"
        value={tier.label}
        onChange={(e) => onChange({ ...tier, label: e.target.value })}
        style={{
          width: 130, padding: "5px 8px", border: "1px solid var(--border-strong)",
          borderRadius: 4, fontSize: 12.5,
        }}
      />
      <span style={{ fontSize: 12, color: "var(--ink-soft)", width: 60 }}>
        {isLast ? "greater than" : "less than"}
      </span>
      {isLast ? (
        <span style={{ width: 90, fontFamily: "var(--font-mono)", fontSize: 12.5, color: "var(--ink-soft)" }}>
          previous ↑
        </span>
      ) : (
        <input
          type="text"
          inputMode="numeric"
          value={text}
          onChange={(e) => handleBoundaryChange(e.target.value)}
          style={{
            width: 90, padding: "5px 8px", border: "1px solid var(--border-strong)",
            borderRadius: 4, fontFamily: "var(--font-mono)", fontSize: 12.5,
          }}
        />
      )}
      <span style={{ fontSize: 12, color: "var(--ink-soft)" }}>mV</span>
      <button
        type="button"
        className="btn btn-danger"
        style={{ padding: "3px 9px", fontSize: 11, marginLeft: "auto" }}
        onClick={onRemove}
        disabled={!canRemove}
        title={canRemove ? "Remove this tier" : "At least 2 tiers are required"}
      >
        Remove
      </button>
    </div>
  );
}

function ColorScalePanel({ tiers, setTiers, open, setOpen }) {
  const updateTier = (index, updated) => {
    setTiers((ts) => ts.map((t, i) => (i === index ? updated : t)));
  };

  return (
    <div className="card" style={{ marginBottom: 12, background: "var(--surface-2)" }}>
      <div
        className="card-title"
        style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer" }}
        onClick={() => setOpen(!open)}
      >
        <span>Color scale settings</span>
        <span className="badge badge-neutral">{open ? "hide ▲" : "customize ▼"}</span>
      </div>

      {open && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: 11.5, color: "var(--ink-soft)", marginBottom: 8 }}>
            Listed worst → best. Each tier applies below its boundary, down to the next tier's.
          </div>

          {tiers.map((tier, i) => (
            <TierRow
              key={tier.id}
              tier={tier}
              index={i}
              isLast={i === tiers.length - 1}
              onChange={(updated) => updateTier(i, updated)}
              onRemove={() => setTiers((ts) => removeTier(ts, tier.id))}
              canRemove={tiers.length > 2}
            />
          ))}

          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={() => setTiers((ts) => addWorstTier(ts))}>
              + Add tier
            </button>
            <button className="btn" onClick={() => setTiers(DEFAULT_TIERS_4)}>
              Reset to 4-tier default
            </button>
            <button className="btn" onClick={() => setTiers(DEFAULT_TIERS_3)}>
              Reset to ASTM C876 (3-tier)
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const escapeHtml = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

// Own component (own draft state) on purpose: if the textarea's text lived in
// ContourMap's state, every keystroke would re-render ContourMap and re-plot
// the whole chart, resetting zoom/pan while the user is just typing a note.
function PointNoteEditor({ point, onSave, onClose }) {
  const [draft, setDraft] = useState(point.description || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const save = async (text) => {
    setSaving(true);
    setError(null);
    try {
      await onSave(text);
      if (!text.trim()) setDraft("");
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="note-editor">
      <div className="note-editor-head">
        <strong>Point {point.col_label}{point.row_label}</strong>
        <span className="badge badge-neutral">{point.value_mv} mV</span>
        <button type="button" className="note-close" onClick={onClose} title="Close">✕</button>
      </div>
      <textarea
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Field note for this point — e.g. visible rust staining, hairline crack, efflorescence…"
        rows={3}
        maxLength={500}
      />
      {error && <div className="error-banner" style={{ marginTop: 8 }}>{error}</div>}
      <div className="btn-row" style={{ marginTop: 10 }}>
        <button className="btn btn-primary" disabled={saving} onClick={() => save(draft)}>
          {saving ? "Saving…" : "Save note"}
        </button>
        {point.description && (
          <button className="btn btn-danger" disabled={saving} onClick={() => save("")}>
            Delete note
          </button>
        )}
        <span style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--ink-soft)" }}>{draft.length}/500</span>
      </div>
    </div>
  );
}

export default function ContourMap({ sessionId, tiers, setTiers }) {
  const [contour, setContour] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getContour(sessionId)
      .then((data) => { if (!cancelled) setContour(data); })
      .catch((err) => { if (!cancelled) setError(err.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (loading) return <Loading label="Interpolating surface…" />;
  if (error) return <div className="card"><div className="error-banner">{error}</div></div>;
  if (!contour) return null;

  const shapes = [];
  contour.rebar_x_mm.forEach((x) => {
    shapes.push({
      type: "line", x0: x, x1: x, y0: 0, y1: Math.max(...contour.y_mm),
      line: { color: "#8a8578", width: 1.2, dash: "dot" },
    });
  });
  contour.rebar_y_mm.forEach((y) => {
    shapes.push({
      type: "line", y0: y, y1: y, x0: 0, x1: Math.max(...contour.x_mm),
      line: { color: "#8a8578", width: 1.2, dash: "dot" },
    });
  });

  const pointColors = contour.points.map((p) => classify(p.value_mv, tiers).color);
  const annotated = contour.points.map((p) => !!p.description);
  const selectedPoint = selectedIndex !== null ? contour.points[selectedIndex] : null;

  // Only the note text changes — the interpolated surface doesn't — so patch
  // the one point in local state instead of refetching (which would flash the
  // loading spinner and throw away the user's current zoom/pan).
  const saveNote = async (text) => {
    const point = contour.points[selectedIndex];
    const updated = await api.setPointDescription(sessionId, point.grid_point_id, text.trim() || null);
    setContour((c) => ({
      ...c,
      points: c.points.map((p, i) => (i === selectedIndex ? { ...p, description: updated.description } : p)),
    }));
  };

  const zFlat = contour.z_mv.flat();
  const zMin = Math.min(...zFlat);
  const zMax = Math.max(...zFlat);
  const contourStep = 50; // matches the standard 50mV convention used in HCP survey reporting
  const contourStart = Math.floor(zMin / contourStep) * contourStep;
  const contourEnd = Math.ceil(zMax / contourStep) * contourStep;

  const xPad = (Math.max(...contour.x_mm) - Math.min(...contour.x_mm)) * 0.06;
  const yPad = (Math.max(...contour.y_mm) - Math.min(...contour.y_mm)) * 0.06;

  return (
    <div className="card">
      <ColorScalePanel tiers={tiers} setTiers={setTiers} open={panelOpen} setOpen={setPanelOpen} />

      <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Contour map</span>
        <span className="badge badge-neutral">interpolation: {contour.method}</span>
      </div>
      <div className="card-subtitle">Dashed lines mark rebar position. Point color = risk tier (customizable above).</div>

      <Plot
        data={[
          {
            x: contour.x_mm,
            y: contour.y_mm,
            z: contour.z_mv,
            type: "contour",
            colorscale: buildRiskColorscale(contourStart, contourEnd, tiers),
            contours: {
              coloring: "fill", showlines: true,
              start: contourStart, end: contourEnd, size: contourStep,
              showlabels: true,
              labelfont: { size: 9, color: "rgba(0,0,0,0.55)" },
            },
            line: { smoothing: 0, width: 0.6, color: "rgba(0,0,0,0.35)" },
            colorbar: { title: { text: "mV", side: "right" }, dtick: contourStep },
            hovertemplate: "x: %{x:.0f}mm<br>y: %{y:.0f}mm<br>%{z:.1f} mV<extra></extra>",
          },
          {
            x: contour.points.map((p) => p.x_mm),
            y: contour.points.map((p) => p.y_mm),
            mode: "markers",
            type: "scatter",
            marker: {
              color: pointColors,
              // annotated points get a bold black ring so notes are visible at a glance;
              // the currently selected point is drawn a little larger
              size: contour.points.map((_, i) => (i === selectedIndex ? 14 : annotated[i] ? 12 : 9)),
              line: {
                color: annotated.map((a) => (a ? "#000000" : "white")),
                width: annotated.map((a) => (a ? 2.5 : 1)),
              },
            },
            text: contour.points.map((p) => {
              const base = `${p.col_label}${p.row_label}: ${p.value_mv} mV`;
              return p.description ? `${base}<br>Note: ${escapeHtml(p.description)}` : base;
            }),
            hovertemplate: "%{text}<extra></extra>",
            showlegend: false,
          },
        ]}
        onClick={(e) => {
          const pt = e.points && e.points[0];
          // curveNumber 1 = the point markers; ignore clicks on the contour fill itself
          if (pt && pt.curveNumber === 1) setSelectedIndex(pt.pointIndex);
        }}
        layout={{
          autosize: true,
          height: 480,
          margin: { l: 50, r: 20, t: 20, b: 40 },
          xaxis: { title: { text: "x (mm)" }, range: [Math.min(...contour.x_mm) - xPad, Math.max(...contour.x_mm) + xPad] },
          yaxis: {
            title: { text: "y (mm)" }, scaleanchor: "x", scaleratio: 1,
            range: [Math.max(...contour.y_mm) + yPad, Math.min(...contour.y_mm) - yPad],
          },
          shapes,
          uirevision: "keep", // keeps the user's zoom/pan when the plot re-renders (select point, save note)
          paper_bgcolor: "transparent",
          plot_bgcolor: "white",
        }}
        style={{ width: "100%" }}
        useResizeHandler
        config={{ displaylogo: false, responsive: true }}
      />

      <div className="risk-legend">
        {tiers.map((tier, i) => (
          <span key={tier.id}>
            <span className="risk-swatch" style={{ background: tier.color }} /> {tier.label} ({tierRangeText(tiers, i)})
          </span>
        ))}
      </div>

      <div className="note-hint">
        Click any point on the map to add a field note — points with a note get a black ring, and
        the note appears in this session's PDF report.
      </div>

      {selectedPoint && (
        <PointNoteEditor
          key={selectedPoint.grid_point_id}
          point={selectedPoint}
          onSave={saveNote}
          onClose={() => setSelectedIndex(null)}
        />
      )}

      {annotated.some(Boolean) && (
        <div className="note-list">
          <div className="note-list-title">Field notes ({annotated.filter(Boolean).length})</div>
          {contour.points.map((p, i) =>
            p.description ? (
              <button key={p.grid_point_id} type="button" className="note-item" onClick={() => setSelectedIndex(i)}>
                <span className="note-item-point">{p.col_label}{p.row_label}</span>
                <span className="note-item-value">{p.value_mv} mV</span>
                <span className="note-item-text">{p.description}</span>
              </button>
            ) : null
          )}
        </div>
      )}
    </div>
  );
}
