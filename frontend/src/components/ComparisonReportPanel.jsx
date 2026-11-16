import React, { useState, useEffect } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
import Plotly from "plotly.js-dist-min";
import { api } from "../api";
import { classify, buildRiskColorscale } from "../lib/riskTiers";

const Plot = createPlotlyComponent(Plotly);

export default function ComparisonReportPanel({ projectId, project, sessions, tiers }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);
  const [sessionData, setSessionData] = useState([]);
  const [includePhotos, setIncludePhotos] = useState(false);

  const eligibleSessions = sessions.filter((s) => s.reading_count > 0);
  const eligibleCount = eligibleSessions.length;
  const tooFew = eligibleCount < 2;

  useEffect(() => {
    let cancelled = false;
    if (tooFew) {
      setSessionData([]);
      return;
    }
    Promise.all(
      eligibleSessions.map(async (s) => {
        try {
          const [st, ct] = await Promise.all([
            api.getStats(s.id),
            api.getContour(s.id).catch(() => null),
          ]);
          return { session: s, stats: st, contour: ct };
        } catch {
          return null;
        }
      })
    ).then((items) => {
      if (!cancelled) {
        setSessionData(items.filter(Boolean));
      }
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, JSON.stringify(eligibleSessions.map((s) => `${s.id}:${s.reading_count}:${s.has_photo}`))]);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      const blob = await api.downloadComparisonReport(projectId, tiers, null, includePhotos);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safeName = project.name.replace(/[^a-z0-9]/gi, "_");
      a.href = url;
      a.download = `${safeName}_comparison_report.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  const xLabels = sessionData.map(({ session }) =>
    session.day_number != null ? `Day ${session.day_number}` : session.survey_date
  );
  const means = sessionData.map(({ stats }) => stats.mean_mv);
  const mins = sessionData.map(({ stats }) => stats.min_mv);
  const maxs = sessionData.map(({ stats }) => stats.max_mv);
  const stds = sessionData.map(({ stats }) => stats.std_mv || 0);
  const stdHigh = means.map((m, i) => Math.min(maxs[i], +(m + stds[i]).toFixed(1)));
  const stdLow = means.map((m, i) => Math.max(mins[i], +(m - stds[i]).toFixed(1)));
  const markerColors = means.map((m) => classify(m, tiers).color);

  const thresholdShapes = tiers
    .slice(0, -1)
    .filter((t) => t.boundary !== null && t.boundary !== undefined)
    .map((t) => ({
      type: "line",
      xref: "paper",
      x0: 0,
      x1: 1,
      yref: "y",
      y0: t.boundary,
      y1: t.boundary,
      line: { color: t.color, width: 1.5, dash: "dash" },
    }));

  const thresholdAnnotations = tiers
    .slice(0, -1)
    .filter((t) => t.boundary !== null && t.boundary !== undefined)
    .map((t) => ({
      xref: "paper",
      x: 0.99,
      yref: "y",
      y: t.boundary,
      text: `${t.label} (<${t.boundary} mV)`,
      showarrow: false,
      xanchor: "right",
      yanchor: "bottom",
      font: { size: 10, color: t.color, family: "JetBrains Mono, monospace" },
      bgcolor: "rgba(255,255,255,0.88)",
      borderpad: 2,
    }));

  return (
    <div className="card card-accent">
      <div className="card-header-row">
        <div>
          <div className="card-title">Compare sessions</div>
          <div className="card-subtitle" style={{ marginBottom: 0 }}>
            {tooFew
              ? "Add readings to at least one more session to unlock a trend comparison across survey dates."
              : `Longitudinal comparison across all ${eligibleCount} sessions — trend trajectory, daily contour maps, summary metrics, and per-point history.`}
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 8 }}>
          <button className="btn btn-primary" onClick={handleDownload} disabled={downloading || tooFew}>
            {downloading ? "Generating PDF…" : "Download comparison report (PDF)"}
          </button>
          {!tooFew && (
            <label style={{ display: "inline-flex", alignItems: "center", gap: 7, cursor: "pointer", fontSize: 12.5, color: "var(--ink)" }}>
              <input
                type="checkbox"
                checked={includePhotos}
                onChange={(e) => setIncludePhotos(e.target.checked)}
                style={{ accentColor: "var(--accent)", cursor: "pointer", width: 15, height: 15 }}
              />
              <span>Also include daily slab photos in report</span>
            </label>
          )}
        </div>
      </div>

      {error && <div className="error-banner" style={{ marginTop: 14 }}>{error}</div>}

      {!tooFew && sessionData.length >= 2 && (
        <div className="comparison-preview">
          <div className="comparison-chart-wrap">
            <Plot
              data={[
                {
                  x: xLabels,
                  y: maxs,
                  type: "scatter",
                  mode: "lines",
                  line: { color: "rgba(27, 110, 110, 0.3)", width: 1, dash: "dot" },
                  hoverinfo: "skip",
                  showlegend: false,
                },
                {
                  x: xLabels,
                  y: mins,
                  type: "scatter",
                  mode: "lines",
                  fill: "tonexty",
                  fillcolor: "rgba(27, 110, 110, 0.11)",
                  line: { color: "rgba(27, 110, 110, 0.3)", width: 1, dash: "dot" },
                  name: "Min–Max range",
                  hovertemplate: "Min: %{y} mV<extra></extra>",
                },
                {
                  x: xLabels,
                  y: stdHigh,
                  type: "scatter",
                  mode: "lines",
                  line: { width: 0 },
                  hoverinfo: "skip",
                  showlegend: false,
                },
                {
                  x: xLabels,
                  y: stdLow,
                  type: "scatter",
                  mode: "lines",
                  fill: "tonexty",
                  fillcolor: "rgba(27, 110, 110, 0.22)",
                  line: { width: 0 },
                  name: "±1 Std dev",
                  hoverinfo: "skip",
                },
                {
                  x: xLabels,
                  y: means,
                  type: "scatter",
                  mode: "lines+markers+text",
                  name: "Mean HCP",
                  line: { color: "#0f5252", width: 3, shape: "spline", smoothing: 0.35 },
                  marker: {
                    size: 11,
                    color: markerColors,
                    line: { color: "#ffffff", width: 2 },
                  },
                  text: means.map((m) => `${m} mV`),
                  textposition: "top center",
                  textfont: { size: 11, family: "JetBrains Mono, monospace", color: "#1f2421" },
                  hovertemplate: "<b>%{x}</b><br>Mean: %{y} mV<extra></extra>",
                },
              ]}
              layout={{
                autosize: true,
                height: 310,
                margin: { l: 54, r: 24, t: 36, b: 42 },
                title: {
                  text: "Mean HCP Over Time (±1 SD & Min–Max Envelope)",
                  font: { size: 13, family: "Inter, sans-serif", color: "#1f2421" },
                  x: 0.01,
                },
                xaxis: {
                  gridcolor: "#ece8dc",
                  zeroline: false,
                  tickfont: { size: 11.5, family: "JetBrains Mono, monospace" },
                },
                yaxis: {
                  title: { text: "mV", font: { size: 11.5 } },
                  gridcolor: "#ece8dc",
                  zeroline: false,
                  tickfont: { size: 11, family: "JetBrains Mono, monospace" },
                },
                shapes: thresholdShapes,
                annotations: thresholdAnnotations,
                legend: { orientation: "h", x: 1, xanchor: "right", y: 1.14, font: { size: 11 } },
                paper_bgcolor: "transparent",
                plot_bgcolor: "#ffffff",
              }}
              style={{ width: "100%" }}
              useResizeHandler
              config={{ displaylogo: false, responsive: true }}
            />
          </div>

          {/* COMPULSORY: Daily Contour Maps Comparison */}
          <div className="comparison-photos-section">
            <div className="comparison-photos-header">
              <span>Daily contour maps ({eligibleCount} sessions) — compulsory</span>
              <span className="comparison-photos-hint">Included side-by-side in comparison report with labels</span>
            </div>
            <div className="comparison-photo-strip">
              {sessionData.map(({ session, stats, contour }) => {
                const label = session.day_number != null ? `Day ${session.day_number}` : session.survey_date;
                const tier = classify(stats.mean_mv, tiers);
                const zFlat = contour?.z_mv ? contour.z_mv.flat() : [];
                const zMin = zFlat.length ? Math.min(...zFlat) : -600;
                const zMax = zFlat.length ? Math.max(...zFlat) : -100;
                const contourStep = 50;
                const contourStart = Math.floor(zMin / contourStep) * contourStep;
                const contourEnd = Math.ceil(zMax / contourStep) * contourStep;

                return (
                  <div key={session.id} className="comparison-photo-card">
                    <div className="comparison-photo-card-top">
                      <strong>{label}</strong>
                      <span>{session.survey_date}</span>
                    </div>
                    <div className="comparison-photo-thumb-wrap" style={{ height: 130, padding: 2 }}>
                      {contour ? (
                        <Plot
                          data={[
                            {
                              x: contour.x_mm,
                              y: contour.y_mm,
                              z: contour.z_mv,
                              type: "contour",
                              colorscale: buildRiskColorscale(contourStart, contourEnd, tiers),
                              contours: {
                                coloring: "fill",
                                showlines: false,
                                start: contourStart,
                                end: contourEnd,
                                size: contourStep,
                              },
                              showscale: false,
                              hoverinfo: "skip",
                            },
                            {
                              x: contour.points.map((p) => p.x_mm),
                              y: contour.points.map((p) => p.y_mm),
                              mode: "markers",
                              type: "scatter",
                              marker: {
                                color: contour.points.map((p) => classify(p.value_mv, tiers).color),
                                size: 5,
                                line: { color: "white", width: 0.5 },
                              },
                              hoverinfo: "skip",
                            },
                          ]}
                          layout={{
                            autosize: true,
                            height: 126,
                            margin: { l: 2, r: 2, t: 2, b: 2 },
                            xaxis: { visible: false },
                            yaxis: {
                              visible: false,
                              scaleanchor: "x",
                              scaleratio: 1,
                              range: [Math.max(...contour.y_mm) + 10, Math.min(...contour.y_mm) - 10],
                            },
                            paper_bgcolor: "transparent",
                            plot_bgcolor: "white",
                          }}
                          style={{ width: "100%", height: "100%" }}
                          config={{ staticPlot: true, responsive: true }}
                        />
                      ) : (
                        <div className="comparison-photo-empty">Contour unavailable</div>
                      )}
                    </div>
                    <div className="comparison-photo-card-foot">
                      <span>Mean: <strong>{stats.mean_mv} mV</strong></span>
                      <span className="comparison-tier-dot" style={{ color: tier.color }}>● {tier.label}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* OPTIONAL: Daily Slab Photos Strip (shown when toggle is on or if user wants to see photos) */}
          {includePhotos && (
            <div className="comparison-photos-section">
              <div className="comparison-photos-header">
                <span>Daily slab images ({eligibleSessions.filter((s) => s.has_photo).length} of {eligibleCount} uploaded) — optional</span>
                <span className="comparison-photos-hint">Included in PDF report per your selection</span>
              </div>
              <div className="comparison-photo-strip">
                {sessionData.map(({ session, stats }) => {
                  const label = session.day_number != null ? `Day ${session.day_number}` : session.survey_date;
                  const tier = classify(stats.mean_mv, tiers);
                  return (
                    <div key={session.id} className="comparison-photo-card">
                      <div className="comparison-photo-card-top">
                        <strong>{label}</strong>
                        <span>{session.survey_date}</span>
                      </div>
                      <div className="comparison-photo-thumb-wrap">
                        {session.has_photo ? (
                          <img
                            src={api.sessionPhotoUrl(session.id)}
                            alt={label}
                            className="comparison-photo-thumb"
                          />
                        ) : (
                          <div className="comparison-photo-empty">No photo uploaded</div>
                        )}
                      </div>
                      <div className="comparison-photo-card-foot">
                        <span>Mean: <strong>{stats.mean_mv} mV</strong></span>
                        <span className="comparison-tier-dot" style={{ color: tier.color }}>● {tier.label}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
