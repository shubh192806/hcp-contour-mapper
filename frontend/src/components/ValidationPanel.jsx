import React, { useEffect, useState } from "react";
import { api } from "../api";

export default function ValidationPanel({ sessionId, refreshKey }) {
  const [result, setResult] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.validateSession(sessionId).then((r) => { if (!cancelled) setResult(r); });
    return () => { cancelled = true; };
  }, [sessionId, refreshKey]);

  if (!result) return null;

  return (
    <div className="card">
      <div className="card-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span>Validation</span>
        {result.ok ? (
          <span className="badge badge-ok">Ready to interpolate</span>
        ) : (
          <span className="badge badge-danger">{result.missing_points} of {result.total_points} points missing</span>
        )}
      </div>

      {result.issues.length === 0 ? (
        <div className="card-subtitle" style={{ margin: 0 }}>No issues found.</div>
      ) : (
        <div className="issue-list">
          {result.issues.slice(0, 20).map((issue, i) => (
            <div key={i} className={`issue-item ${issue.severity}`}>
              <strong>{issue.col_label ?? ""}{issue.row_label ?? ""}</strong> {issue.message}
            </div>
          ))}
          {result.issues.length > 20 && (
            <div className="card-subtitle">+ {result.issues.length - 20} more</div>
          )}
        </div>
      )}

      <div className="btn-row">
        <a className="btn" href={api.exportUrl(sessionId)} download>
          Export readings (Excel)
        </a>
      </div>
    </div>
  );
}
