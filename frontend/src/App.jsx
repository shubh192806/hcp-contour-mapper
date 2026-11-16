import React, { useEffect, useState, useCallback } from "react";
import { api } from "./api";
import ProjectSetup from "./components/ProjectSetup";
import ProjectWorkspace from "./components/ProjectWorkspace";

export default function App() {
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [creatingNew, setCreatingNew] = useState(false);
  const [loading, setLoading] = useState(true);

  const refreshProjects = useCallback(async () => {
    const data = await api.listProjects();
    setProjects(data);
    return data;
  }, []);

  useEffect(() => {
    refreshProjects()
      .then((data) => {
        if (data.length && !selectedId) setSelectedId(data[0].id);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCreated = async (project) => {
    await refreshProjects();
    setSelectedId(project.id);
    setCreatingNew(false);
  };

  const handleSelect = (id) => {
    setSelectedId(id);
    setCreatingNew(false);
  };

  const handleDeleted = async (id) => {
    await api.deleteProject(id);
    const data = await refreshProjects();
    if (selectedId === id) {
      setSelectedId(data.length ? data[0].id : null);
    }
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark-icon">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M3 17L9 11L13 15L21 6" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="3" cy="17" r="1.6" fill="white" />
              <circle cx="9" cy="11" r="1.6" fill="white" />
              <circle cx="13" cy="15" r="1.6" fill="white" />
              <circle cx="21" cy="6" r="1.6" fill="white" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-mark">Corrosion assessment</span>
            <span className="brand-title">HCP Contour Mapper</span>
          </div>
        </div>

        <button className="btn-new-project" onClick={() => setCreatingNew(true)}>
          + New project
        </button>

        <nav className="project-nav">
          {projects.map((p) => (
            <div
              key={p.id}
              className={`project-nav-item ${!creatingNew && p.id === selectedId ? "active" : ""}`}
              onClick={() => handleSelect(p.id)}
            >
              <span className="project-nav-item-name">{p.name}</span>
              <span className="project-nav-item-meta">
                {p.grid_rows}×{p.grid_cols} grid · {p.session_count} session{p.session_count === 1 ? "" : "s"}
                {!p.grid_confirmed && " · draft"}
              </span>
            </div>
          ))}
          {!loading && projects.length === 0 && (
            <div className="project-nav-item-meta" style={{ padding: "8px 10px" }}>
              No projects yet.
            </div>
          )}
        </nav>
      </aside>

      <main className="main-area">
        {creatingNew && <ProjectSetup onCreated={handleCreated} onCancel={() => setCreatingNew(false)} />}

        {!creatingNew && selectedId && (
          <ProjectWorkspace
            key={selectedId}
            projectId={selectedId}
            onDeleted={() => handleDeleted(selectedId)}
          />
        )}

        {!creatingNew && !selectedId && !loading && (
          <div className="empty-state">
            <div className="empty-state-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
                <rect x="3" y="3" width="18" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
                <path d="M3 9h18M3 15h18M9 3v18M15 3v18" stroke="currentColor" strokeWidth="1" opacity="0.4" />
                <circle cx="9" cy="9" r="1.4" fill="currentColor" />
                <circle cx="15" cy="15" r="1.4" fill="currentColor" />
              </svg>
            </div>
            <h3>No project selected</h3>
            <p>Create a project to define a slab's geometry and measurement grid.</p>
            <button className="btn btn-primary" onClick={() => setCreatingNew(true)} style={{ marginTop: 14 }}>
              + New project
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
