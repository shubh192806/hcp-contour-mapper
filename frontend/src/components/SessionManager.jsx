import React, { useState } from "react";
import { api } from "../api";

export default function SessionManager({ projectId, sessions, selectedSessionId, onSelect, onChanged }) {
  const [showForm, setShowForm] = useState(sessions.length === 0);
  const [form, setForm] = useState({ day_number: "", survey_date: new Date().toISOString().slice(0, 10), label: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleCreate = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        survey_date: form.survey_date,
        day_number: form.day_number === "" ? null : Number(form.day_number),
        label: form.label || null,
      };
      const session = await api.createSession(projectId, payload);
      setForm({ day_number: "", survey_date: new Date().toISOString().slice(0, 10), label: "" });
      setShowForm(false);
      await onChanged();
      onSelect(session.id);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("Delete this session and all its readings?")) return;
    await api.deleteSession(id);
    await onChanged();
    if (selectedSessionId === id) onSelect(null);
  };

  return (
    <div className="card">
      <div className="card-title">Survey sessions</div>
      <div className="card-subtitle">
        Each session is one site visit. All sessions reuse the same confirmed grid, so contour maps line up
        exactly across dates.
      </div>

      {sessions.length > 0 && (
        <div className="session-pills">
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`session-pill ${s.id === selectedSessionId ? "active" : ""}`}
              onClick={() => onSelect(s.id)}
            >
              {s.day_number != null ? `Day ${s.day_number}` : s.survey_date} · {s.reading_count} pts
              <span
                onClick={(e) => { e.stopPropagation(); handleDelete(s.id); }}
                style={{ marginLeft: 8, opacity: 0.6 }}
                title="Delete session"
              >
                ✕
              </span>
            </div>
          ))}
        </div>
      )}

      {!showForm && (
        <button className="btn" onClick={() => setShowForm(true)}>
          + New session
        </button>
      )}

      {showForm && (
        <form onSubmit={handleCreate} className="form-grid cols-3" style={{ marginTop: sessions.length ? 4 : 0 }}>
          <div className="form-field">
            <label>Survey date</label>
            <input
              type="date"
              value={form.survey_date}
              onChange={(e) => setForm((f) => ({ ...f, survey_date: e.target.value }))}
              required
            />
          </div>
          <div className="form-field">
            <label>Day number (optional)</label>
            <input
              type="number"
              value={form.day_number}
              onChange={(e) => setForm((f) => ({ ...f, day_number: e.target.value }))}
              placeholder="e.g. 1"
            />
          </div>
          <div className="form-field">
            <label>Label (optional)</label>
            <input
              value={form.label}
              onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
              placeholder="Before saturation"
            />
          </div>
          <div className="form-field span-2" style={{ flexDirection: "row", gap: 10, alignItems: "flex-end" }}>
            <button type="submit" className="btn btn-primary" disabled={submitting}>
              {submitting ? "Creating…" : "Create session"}
            </button>
            {sessions.length > 0 && (
              <button type="button" className="btn" onClick={() => setShowForm(false)}>
                Cancel
              </button>
            )}
          </div>
        </form>
      )}
      {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}
    </div>
  );
}
