import React, { useEffect, useState, useCallback } from "react";
import { api } from "../api";
import GridPreview from "./GridPreview";
import SessionManager from "./SessionManager";
import DataEntryGrid from "./DataEntryGrid";
import ContourMap from "./ContourMap";
import StatsPanel from "./StatsPanel";
import ValidationPanel from "./ValidationPanel";
import ReportPanel from "./ReportPanel";
import ComparisonReportPanel from "./ComparisonReportPanel";
import SlabPhoto from "./SlabPhoto";
import Loading from "./Loading";
import { DEFAULT_TIERS_4 } from "../lib/riskTiers";

const tiersStorageKey = (projectId) => `hcp-tiers:${projectId}`;

export default function ProjectWorkspace({ projectId, onDeleted }) {
  const [project, setProject] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [selectedSessionId, setSelectedSessionId] = useState(null);
  const [tab, setTab] = useState("sessions");
  const [refreshKey, setRefreshKey] = useState(0);

  // Color-scale tiers live here (not inside ContourMap) so the contour map
  // and the stats panel always classify points against the exact same
  // scheme. Persisted per-project in localStorage so a customization
  // survives a page reload or switching sessions.
  const [tiers, setTiersState] = useState(() => {
    try {
      const saved = localStorage.getItem(tiersStorageKey(projectId));
      return saved ? JSON.parse(saved) : DEFAULT_TIERS_4;
    } catch {
      return DEFAULT_TIERS_4;
    }
  });

  const setTiers = useCallback((updater) => {
    setTiersState((prev) => {
      const next = typeof updater === "function" ? updater(prev) : updater;
      try {
        localStorage.setItem(tiersStorageKey(projectId), JSON.stringify(next));
      } catch {
        // localStorage unavailable (private browsing, quota) — customization
        // just won't persist across reloads, not worth failing the update over.
      }
      return next;
    });
  }, [projectId]);

  const loadProject = useCallback(async () => {
    const p = await api.getProject(projectId);
    setProject(p);
    return p;
  }, [projectId]);

  const loadSessions = useCallback(async () => {
    const s = await api.listSessions(projectId);
    setSessions(s);
    return s;
  }, [projectId]);

  useEffect(() => {
    loadProject();
    loadSessions().then((s) => {
      if (s.length) setSelectedSessionId(s[0].id);
      else setSelectedSessionId(null);
    });
    setTab("sessions");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const handleGridConfirmed = async (updated) => {
    setProject(updated);
  };

  const handleSessionsChanged = async () => {
    await loadSessions();
    setRefreshKey((k) => k + 1);
  };

  const handleDataSaved = async () => {
    await loadSessions();
    setRefreshKey((k) => k + 1);
  };

  if (!project) return <Loading label="Loading project…" />;

  if (!project.grid_confirmed) {
    return (
      <div>
        <div className="page-header">
          <h1 className="page-title">{project.name}</h1>
          <p className="page-subtitle">Confirm the measurement grid before recording any readings.</p>
        </div>
        <GridPreview project={project} onConfirmed={handleGridConfirmed} />
      </div>
    );
  }

  const selectedSession = sessions.find((s) => s.id === selectedSessionId);

  return (
    <div>
      <div className="workspace-banner">
        <div>
          <h1 className="page-title">{project.name}</h1>
          <div className="meta-chips">
            <span className="meta-chip">
              <strong>{project.grid_rows}×{project.grid_cols}</strong> grid ({project.grid_points?.length || 0} pts)
            </span>
            <span className="meta-chip">
              <strong>{project.grid_pitch_x_mm}×{project.grid_pitch_y_mm} mm</strong> pitch
            </span>
            {project.cover_depth_mm && (
              <span className="meta-chip">
                <strong>{project.cover_depth_mm} mm</strong> cover
              </span>
            )}
            <span className="meta-chip">
              <strong>{project.reference_electrode}</strong> reference electrode
            </span>
          </div>
        </div>
        <button className="btn btn-danger" onClick={onDeleted}>Delete project</button>
      </div>

      <div className="tabs">
        <button className={`tab ${tab === "sessions" ? "active" : ""}`} onClick={() => setTab("sessions")}>
          Sessions &amp; data entry
          <span className="tab-count">{sessions.length}</span>
        </button>
        <button
          className={`tab ${tab === "analysis" ? "active" : ""}`}
          onClick={() => setTab("analysis")}
          disabled={!selectedSessionId}
        >
          Contour &amp; analysis
        </button>
      </div>

      {tab === "sessions" && (
        <>
          <SessionManager
            projectId={projectId}
            sessions={sessions}
            selectedSessionId={selectedSessionId}
            onSelect={setSelectedSessionId}
            onChanged={handleSessionsChanged}
          />
          {selectedSessionId && (
            <>
              <DataEntryGrid project={project} sessionId={selectedSessionId} onSaved={handleDataSaved} />
              <SlabPhoto
                sessionId={selectedSessionId}
                hasPhoto={!!selectedSession?.has_photo}
                onChanged={handleSessionsChanged}
              />
            </>
          )}
        </>
      )}

      {tab === "analysis" && selectedSessionId && (
        <>
          {sessions.length > 1 && (
            <div className="session-pills">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`session-pill ${s.id === selectedSessionId ? "active" : ""}`}
                  onClick={() => setSelectedSessionId(s.id)}
                >
                  <span>{s.day_number != null ? `Day ${s.day_number}` : s.survey_date}</span>
                  <span className="session-pill-sub">{s.reading_count} pts{s.has_photo ? " · 📷" : ""}</span>
                </div>
              ))}
            </div>
          )}
          <ValidationPanel sessionId={selectedSessionId} refreshKey={refreshKey} />
          {selectedSession?.reading_count > 0 && (
            <>
              <ContourMap
                key={`${selectedSessionId}-${refreshKey}`}
                sessionId={selectedSessionId}
                tiers={tiers}
                setTiers={setTiers}
              />
              <StatsPanel
                key={`stats-${selectedSessionId}-${refreshKey}`}
                sessionId={selectedSessionId}
                tiers={tiers}
              />
              <ReportPanel
                sessionId={selectedSessionId}
                project={project}
                session={selectedSession}
                tiers={tiers}
              />
              <ComparisonReportPanel
                projectId={projectId}
                project={project}
                sessions={sessions}
                tiers={tiers}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}
