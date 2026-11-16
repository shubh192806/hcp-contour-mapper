import React, { useState } from "react";
import { api } from "../api";

export default function SlabPhoto({ sessionId, hasPhoto, onChanged }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [cacheKey, setCacheKey] = useState(() => Date.now());

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadSessionPhoto(sessionId, file);
      setCacheKey(Date.now()); // bust the <img> cache so the new photo actually shows
      onChanged();
    } catch (err) {
      setError(err.message);
    } finally {
      setUploading(false);
    }
    e.target.value = "";
  };

  const handleRemove = async () => {
    if (!confirm("Remove this session's slab photo?")) return;
    setError(null);
    try {
      await api.deleteSessionPhoto(sessionId);
      onChanged();
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="card">
      <div className="card-title">Slab photo</div>
      <div className="card-subtitle">
        Optional — included in this session's PDF report alongside the contour map.
      </div>

      {hasPhoto ? (
        <div>
          <img
            src={`${api.sessionPhotoUrl(sessionId)}?t=${cacheKey}`}
            alt="Slab"
            style={{
              maxWidth: "100%", maxHeight: 320, borderRadius: 8,
              border: "1px solid var(--border)", display: "block",
            }}
          />
          <div className="btn-row">
            <label className="btn" style={{ cursor: "pointer" }}>
              Replace photo
              <input type="file" accept="image/*" onChange={handleUpload} style={{ display: "none" }} />
            </label>
            <button className="btn btn-danger" onClick={handleRemove}>Remove</button>
          </div>
        </div>
      ) : (
        <div className="upload-drop">
          <label style={{ cursor: "pointer" }}>
            <strong>{uploading ? "Uploading…" : "Upload a photo"}</strong> — JPG, PNG, WEBP, or HEIC, up to 15MB
            <input type="file" accept="image/*" onChange={handleUpload} style={{ display: "none" }} disabled={uploading} />
          </label>
        </div>
      )}

      {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}
    </div>
  );
}
