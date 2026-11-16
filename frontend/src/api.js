// In local dev, Vite's proxy forwards /api/* to the backend (see vite.config.js),
// so a relative path works. In production the frontend and backend are usually
// on different hosts (e.g. Vercel + Render), so VITE_API_BASE_URL must be set
// to the backend's real URL at build time — see .env.example.
const BASE = `${import.meta.env.VITE_API_BASE_URL || ""}/api`;

async function handle(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

export const api = {
  listProjects: () => fetch(`${BASE}/projects`).then(handle),
  getProject: (id) => fetch(`${BASE}/projects/${id}`).then(handle),
  createProject: (payload) =>
    fetch(`${BASE}/projects`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(handle),
  deleteProject: (id) => fetch(`${BASE}/projects/${id}`, { method: "DELETE" }).then(handle),
  confirmGrid: (id, points, excludedPointIds = []) =>
    fetch(`${BASE}/projects/${id}/grid/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ points, excluded_point_ids: excludedPointIds }),
    }).then(handle),

  listSessions: (projectId) => fetch(`${BASE}/projects/${projectId}/sessions`).then(handle),
  createSession: (projectId, payload) =>
    fetch(`${BASE}/projects/${projectId}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }).then(handle),
  deleteSession: (id) => fetch(`${BASE}/sessions/${id}`, { method: "DELETE" }).then(handle),

  getReadings: (sessionId) => fetch(`${BASE}/sessions/${sessionId}/readings`).then(handle),
  setReadings: (sessionId, readings) =>
    fetch(`${BASE}/sessions/${sessionId}/readings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ readings }),
    }).then(handle),
  uploadReadings: (sessionId, file) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/sessions/${sessionId}/upload`, { method: "POST", body: form }).then(handle);
  },

  setPointDescription: (sessionId, gridPointId, description) =>
    fetch(`${BASE}/sessions/${sessionId}/points/${gridPointId}/description`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ description }),
    }).then(handle),

  validateSession: (sessionId) => fetch(`${BASE}/sessions/${sessionId}/validate`).then(handle),
  getContour: (sessionId) => fetch(`${BASE}/sessions/${sessionId}/contour`).then(handle),
  getStats: (sessionId) => fetch(`${BASE}/sessions/${sessionId}/stats`).then(handle),
  exportUrl: (sessionId) => `${BASE}/sessions/${sessionId}/export`,

  // PDF report: POST because the current tier scheme (colors/boundaries) has
  // to travel in the body, so a plain <a href> download link won't work —
  // caller gets a Blob back and triggers the save itself.
  downloadReport: async (sessionId, tiers) => {
    const res = await fetch(`${BASE}/sessions/${sessionId}/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tiers }),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return res.blob();
  },

  downloadComparisonReport: async (projectId, tiers, sessionIds = null, includePhotos = false) => {
    const res = await fetch(`${BASE}/projects/${projectId}/comparison-report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tiers, session_ids: sessionIds, include_photos: includePhotos }),
    });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return res.blob();
  },

  uploadSessionPhoto: (sessionId, file) => {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${BASE}/sessions/${sessionId}/photo`, { method: "POST", body: form }).then(handle);
  },
  sessionPhotoUrl: (sessionId) => `${BASE}/sessions/${sessionId}/photo`,
  deleteSessionPhoto: (sessionId) =>
    fetch(`${BASE}/sessions/${sessionId}/photo`, { method: "DELETE" }).then(handle),
};
