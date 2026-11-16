import React, { useState } from "react";
import { api } from "../api";

export default function ReportPanel({ sessionId, project, session, tiers }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState(null);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);
    try {
      const blob = await api.downloadReport(sessionId, tiers);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      const safeName = project.name.replace(/[^a-z0-9]/gi, "_");
      const label = session?.day_number != null ? `day${session.day_number}` : session?.survey_date;
      a.href = url;
      a.download = `${safeName}_${label}_report.pdf`;
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

  return (
    <div className="card">
      <div className="card-header-row">
        <div>
          <div className="card-title">Single-session report</div>
          <div className="card-subtitle" style={{ marginBottom: 0 }}>
            A complete PDF deliverable for this session — project configuration, slab photo, contour map,
            summary statistics, and risk classification breakdown.
          </div>
        </div>
        <button className="btn btn-primary" onClick={handleDownload} disabled={downloading}>
          {downloading ? "Generating…" : "Download report (PDF)"}
        </button>
      </div>
      {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}
    </div>
  );
}
