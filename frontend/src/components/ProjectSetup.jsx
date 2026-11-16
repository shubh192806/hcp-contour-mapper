import React, { useState } from "react";
import { api } from "../api";

const initial = {
  name: "",
  description: "",
  slab_width_mm: "",
  slab_height_mm: "",
  rebar_rows: 4,
  rebar_cols: 4,
  rebar_pitch_mm: 150,
  rebar_diameter_mm: 10,
  cover_depth_mm: 50,
  grid_rows: 9,
  grid_cols: 9,
  grid_pitch_x_mm: 75,
  grid_pitch_y_mm: 75,
  reference_electrode: "CSE",
};

export default function ProjectSetup({ onCreated, onCancel }) {
  const [form, setForm] = useState(initial);
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const update = (key) => (e) => {
    const raw = e.target.value;
    setForm((f) => ({ ...f, [key]: raw }));
  };

  const totalPoints = (Number(form.grid_rows) || 0) * (Number(form.grid_cols) || 0);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!form.name.trim()) {
      setError("Give the project a name.");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        slab_width_mm: form.slab_width_mm === "" ? null : Number(form.slab_width_mm),
        slab_height_mm: form.slab_height_mm === "" ? null : Number(form.slab_height_mm),
        rebar_rows: Number(form.rebar_rows),
        rebar_cols: Number(form.rebar_cols),
        rebar_pitch_mm: Number(form.rebar_pitch_mm),
        rebar_diameter_mm: form.rebar_diameter_mm === "" ? null : Number(form.rebar_diameter_mm),
        cover_depth_mm: form.cover_depth_mm === "" ? null : Number(form.cover_depth_mm),
        grid_rows: Number(form.grid_rows),
        grid_cols: Number(form.grid_cols),
        grid_pitch_x_mm: Number(form.grid_pitch_x_mm),
        grid_pitch_y_mm: Number(form.grid_pitch_y_mm),
      };
      const project = await api.createProject(payload);
      onCreated(project);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">New project</h1>
        <p className="page-subtitle">
          Configuration set here is fixed once the grid is confirmed. Session data (survey dates, readings) is
          added afterward and can be repeated indefinitely.
        </p>
      </div>

      <form className="card" onSubmit={handleSubmit}>
        <div className="section-divider">Project</div>
        <div className="form-grid">
          <div className="form-field span-2">
            <label>Project name</label>
            <input value={form.name} onChange={update("name")} placeholder="e.g. Slab 1 — 20mm cover" />
          </div>
          <div className="form-field span-2">
            <label>Description (optional)</label>
            <input value={form.description} onChange={update("description")} placeholder="Notes for the report" />
          </div>
          <div className="form-field">
            <label>Slab width (mm)</label>
            <input type="number" value={form.slab_width_mm} onChange={update("slab_width_mm")} placeholder="750" />
          </div>
          <div className="form-field">
            <label>Slab height (mm)</label>
            <input type="number" value={form.slab_height_mm} onChange={update("slab_height_mm")} placeholder="750" />
          </div>
        </div>

        <div className="section-divider">Reinforcement layout</div>
        <p className="card-subtitle" style={{ marginTop: -8 }}>
          Assumes a constant rod pitch for now. Used to overlay rebar position on the contour map — not the
          measurement grid itself.
        </p>
        <div className="form-grid cols-3">
          <div className="form-field">
            <label>Rods (row direction)</label>
            <input type="number" min="2" value={form.rebar_rows} onChange={update("rebar_rows")} />
          </div>
          <div className="form-field">
            <label>Rods (column direction)</label>
            <input type="number" min="2" value={form.rebar_cols} onChange={update("rebar_cols")} />
          </div>
          <div className="form-field">
            <label>Rod pitch (mm)</label>
            <input type="number" value={form.rebar_pitch_mm} onChange={update("rebar_pitch_mm")} />
          </div>
          <div className="form-field">
            <label>Rod diameter (mm)</label>
            <input type="number" value={form.rebar_diameter_mm} onChange={update("rebar_diameter_mm")} />
          </div>
          <div className="form-field">
            <label>Cover depth (mm)</label>
            <input type="number" value={form.cover_depth_mm} onChange={update("cover_depth_mm")} />
          </div>
          <div className="form-field">
            <label>Reference electrode</label>
            <select value={form.reference_electrode} onChange={update("reference_electrode")}>
              <option value="CSE">Cu/CuSO₄ (CSE)</option>
              <option value="SCE">Saturated calomel (SCE)</option>
              <option value="Ag/AgCl">Silver/silver chloride</option>
            </select>
            <span className="hint">ASTM C876 thresholds used here assume CSE.</span>
          </div>
        </div>

        <div className="section-divider">HCP measurement grid</div>
        <p className="card-subtitle" style={{ marginTop: -8 }}>
          Independent of the rebar layout above — this is the actual survey grid walked on site.
        </p>
        <div className="form-grid cols-3">
          <div className="form-field">
            <label>Grid rows</label>
            <input type="number" min="2" value={form.grid_rows} onChange={update("grid_rows")} />
          </div>
          <div className="form-field">
            <label>Grid columns</label>
            <input type="number" min="2" value={form.grid_cols} onChange={update("grid_cols")} />
          </div>
          <div className="form-field">
            <label>Total points</label>
            <input value={totalPoints} disabled />
          </div>
          <div className="form-field">
            <label>Grid pitch X (mm)</label>
            <input type="number" value={form.grid_pitch_x_mm} onChange={update("grid_pitch_x_mm")} />
          </div>
          <div className="form-field">
            <label>Grid pitch Y (mm)</label>
            <input type="number" value={form.grid_pitch_y_mm} onChange={update("grid_pitch_y_mm")} />
            <span className="hint">75mm matches the standard HCP survey pitch.</span>
          </div>
        </div>

        {error && <div className="error-banner" style={{ marginTop: 18 }}>{error}</div>}

        <div className="btn-row">
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Generating grid…" : "Generate grid"}
          </button>
          <button type="button" className="btn" onClick={onCancel}>
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
