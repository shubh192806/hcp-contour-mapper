import React, { useEffect, useState, useMemo, useCallback } from "react";
import { api } from "../api";
import Loading from "./Loading";

export default function DataEntryGrid({ project, sessionId, onSaved }) {
  const rowLabels = useMemo(() => {
    const arr = new Array(project.grid_rows).fill("");
    project.grid_points.forEach((p) => { arr[p.row_index] = p.row_label; });
    return arr;
  }, [project]);
  const colLabels = useMemo(() => {
    const arr = new Array(project.grid_cols).fill("");
    project.grid_points.forEach((p) => { arr[p.col_index] = p.col_label; });
    return arr;
  }, [project]);

  const pointGrid = useMemo(() => {
    const grid = Array.from({ length: project.grid_rows }, () => new Array(project.grid_cols).fill(null));
    project.grid_points.forEach((p) => { grid[p.row_index][p.col_index] = p; });
    return grid;
  }, [project]);

  const [values, setValues] = useState({}); // grid_point_id -> string
  const [flagged, setFlagged] = useState({}); // grid_point_id -> {flagged, reason}
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [uploadMsg, setUploadMsg] = useState(null);

  const loadReadings = useCallback(async () => {
    setLoading(true);
    try {
      const readings = await api.getReadings(sessionId);
      const v = {}, f = {};
      readings.forEach((r) => {
        v[r.grid_point_id] = String(r.value_mv);
        f[r.grid_point_id] = { flagged: r.flagged, reason: r.flag_reason };
      });
      setValues(v);
      setFlagged(f);
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => { loadReadings(); }, [loadReadings]);

  const handleChange = (pointId, raw) => {
    setValues((v) => ({ ...v, [pointId]: raw }));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const readings = Object.entries(values)
        .filter(([, v]) => v !== "" && v !== null && v !== undefined)
        .map(([grid_point_id, v]) => ({ grid_point_id: Number(grid_point_id), value_mv: Number(v) }));
      await api.setReadings(sessionId, readings);
      await loadReadings();
      onSaved();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setError(null);
    setUploadMsg(null);
    try {
      await api.uploadReadings(sessionId, file);
      await loadReadings();
      onSaved();
      setUploadMsg(`Imported readings from ${file.name}`);
    } catch (err) {
      setError(err.message);
    }
    e.target.value = "";
  };

  const filledCount = Object.values(values).filter((v) => v !== "" && v !== null).length;
  const totalCount = project.grid_points.length;

  if (loading) return <Loading label="Loading readings…" />;

  return (
    <div className="card">
      <div className="card-title">Enter readings</div>
      <div className="card-subtitle">
        {filledCount} / {totalCount} points filled. All values in mV.
      </div>

      <div className="upload-drop" style={{ marginBottom: 18 }}>
        <label style={{ cursor: "pointer" }}>
          <strong>Upload CSV / XLSX</strong> — columns: row_label, col_label, value_mv (or reading_1/2/3)
          <input type="file" accept=".csv,.xlsx,.xls" onChange={handleUpload} style={{ display: "none" }} />
        </label>
      </div>
      {uploadMsg && <div className="badge badge-ok" style={{ marginBottom: 12 }}>{uploadMsg}</div>}

      <div style={{ overflowX: "auto" }}>
        <table className="data-table">
          <thead>
            <tr>
              <th></th>
              {colLabels.map((c, i) => <th key={i}>{c}</th>)}
            </tr>
          </thead>
          <tbody>
            {pointGrid.map((row, ri) => (
              <tr key={ri}>
                <td className="axis-label">{rowLabels[ri]}</td>
                {row.map((point, ci) => {
                  if (!point) {
                    return <td key={ci} className="excluded" title="Not part of this survey grid" />;
                  }
                  const f = flagged[point.id];
                  const cellClass = f?.flagged ? "flagged" : "";
                  return (
                    <td key={ci} className={cellClass} title={f?.flagged ? f.reason : ""}>
                      <input
                        type="number"
                        step="any"
                        value={values[point.id] ?? ""}
                        onChange={(e) => handleChange(point.id, e.target.value)}
                        placeholder="—"
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {error && <div className="error-banner" style={{ marginTop: 16 }}>{error}</div>}

      <div className="btn-row">
        <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "Save readings"}
        </button>
      </div>
    </div>
  );
}
