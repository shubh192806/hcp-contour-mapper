import React, { useEffect, useState } from "react";
import { api } from "../api";
import { classify } from "../lib/riskTiers";

export default function StatsPanel({ sessionId, tiers }) {
  const [numeric, setNumeric] = useState(null);
  const [readings, setReadings] = useState(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getStats(sessionId), api.getReadings(sessionId)]).then(([s, r]) => {
      if (cancelled) return;
      setNumeric(s);
      setReadings(r);
    });
    return () => { cancelled = true; };
  }, [sessionId]);

  if (!numeric || numeric.count === 0 || !readings) return null;

  const counts = {};
  tiers.forEach((t) => { counts[t.id] = 0; });
  readings.forEach((r) => { counts[classify(r.value_mv, tiers).id] += 1; });

  return (
    <div className="card">
      <div className="card-header-row" style={{ marginBottom: 14 }}>
        <div>
          <div className="card-title">Summary statistics</div>
          <div className="card-subtitle" style={{ marginBottom: 0 }}>
            Statistical distribution and risk-tier breakdown across all {numeric.count} measured points.
          </div>
        </div>
        <span className="badge badge-neutral">{numeric.count} active points</span>
      </div>

      <div className="stat-row">
        <div className="stat-box stat-box-featured">
          <div className="stat-label">Mean potential</div>
          <div className="stat-value">{numeric.mean_mv} <span className="stat-unit">mV</span></div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Std dev</div>
          <div className="stat-value">{numeric.std_mv} <span className="stat-unit">mV</span></div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Min (most negative)</div>
          <div className="stat-value">{numeric.min_mv} <span className="stat-unit">mV</span></div>
        </div>
        <div className="stat-box">
          <div className="stat-label">Max (least negative)</div>
          <div className="stat-value">{numeric.max_mv} <span className="stat-unit">mV</span></div>
        </div>
      </div>

      <div className="tier-progress-wrap">
        <div className="tier-progress-bar">
          {tiers.map((tier) => {
            const c = counts[tier.id] || 0;
            if (c === 0) return null;
            const pct = (c / numeric.count) * 100;
            return (
              <div
                key={tier.id}
                className="tier-progress-segment"
                style={{ width: `${pct}%`, background: tier.color }}
                title={`${tier.label}: ${c} points (${pct.toFixed(1)}%)`}
              />
            );
          })}
        </div>
      </div>

      <div className="stat-row" style={{ gridTemplateColumns: `repeat(${tiers.length + 1}, 1fr)`, marginBottom: 0 }}>
        {tiers.map((tier) => {
          const c = counts[tier.id] || 0;
          const pct = Math.round((c / numeric.count) * 100);
          return (
            <div className="stat-box" key={tier.id} style={{ borderTop: `3px solid ${tier.color}` }}>
              <div className="stat-label">{tier.label}</div>
              <div className="stat-value-row">
                <span className="stat-value" style={{ color: tier.color }}>{c}</span>
                <span className="stat-pct">{pct}%</span>
              </div>
            </div>
          );
        })}
        <div className="stat-box" style={{ borderTop: "3px solid var(--ink-soft)" }}>
          <div className="stat-label">Total points</div>
          <div className="stat-value-row">
            <span className="stat-value">{numeric.count}</span>
            <span className="stat-pct">100%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
