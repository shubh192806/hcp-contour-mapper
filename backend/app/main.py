import io
import os
from datetime import datetime
from typing import List

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, FileResponse
from sqlalchemy.orm import Session as DBSession, joinedload
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from . import models, schemas, grid, interpolation, validation, parser, report
from .database import Base, engine, get_db, run_light_migrations

Base.metadata.create_all(bind=engine)
run_light_migrations()

UPLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "sessions")
os.makedirs(UPLOADS_DIR, exist_ok=True)

app = FastAPI(
    title="HCP Contour Mapper",
    description="Automates half-cell potential contour mapping for reinforced concrete corrosion assessment.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- projects

@app.post("/api/projects", response_model=schemas.ProjectOut)
def create_project(payload: schemas.ProjectCreate, db: DBSession = Depends(get_db)):
    project = models.Project(**payload.model_dump())
    db.add(project)
    db.commit()
    db.refresh(project)

    points = grid.generate_grid_points(
        project.grid_rows, project.grid_cols, project.grid_pitch_x_mm, project.grid_pitch_y_mm
    )
    for p in points:
        db.add(models.GridPoint(project_id=project.id, **p))
    db.commit()
    db.refresh(project)
    return project


@app.get("/api/projects", response_model=List[schemas.ProjectSummary])
def list_projects(db: DBSession = Depends(get_db)):
    projects = db.query(models.Project).order_by(models.Project.created_at.desc()).all()
    out = []
    for p in projects:
        d = schemas.ProjectSummary.model_validate(p).model_dump()
        d["session_count"] = len(p.sessions)
        out.append(d)
    return out


@app.get("/api/projects/{project_id}", response_model=schemas.ProjectOut)
def get_project(project_id: int, db: DBSession = Depends(get_db)):
    project = db.query(models.Project).options(joinedload(models.Project.grid_points)).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: DBSession = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    db.delete(project)
    db.commit()
    return {"ok": True}


@app.post("/api/projects/{project_id}/grid/confirm", response_model=schemas.ProjectOut)
def confirm_grid(project_id: int, payload: schemas.GridConfirm, db: DBSession = Depends(get_db)):
    """
    Apply any label renames the user made while reviewing the generated grid,
    optionally remove points that don't actually exist in the real survey
    (irregular layouts — not every row/column intersection is necessarily
    measured), then lock the grid in.

    Point removal is only allowed before any session has been created. Once
    readings exist, deleting a point would silently corrupt historical data
    across sessions, so that path is blocked — start a new project instead.
    """
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    if payload.excluded_point_ids and len(project.sessions) > 0:
        raise HTTPException(
            400,
            "Cannot remove grid points after sessions have been created for this project. "
            "Grid shape must be finalized before recording readings — start a new project "
            "if the layout needs to change.",
        )

    excluded_ids = set(payload.excluded_point_ids)
    for point_id in excluded_ids:
        gp = db.get(models.GridPoint, point_id)
        if gp and gp.project_id == project_id:
            db.delete(gp)

    for rename in payload.points:
        if rename.id in excluded_ids:
            continue  # being deleted anyway, no point renaming it
        gp = db.get(models.GridPoint, rename.id)
        if not gp or gp.project_id != project_id:
            continue
        if rename.row_label is not None:
            gp.row_label = rename.row_label
        if rename.col_label is not None:
            gp.col_label = rename.col_label

    project.grid_confirmed = True
    db.commit()
    db.refresh(project)
    return project


# ---------------------------------------------------------------- sessions

@app.post("/api/projects/{project_id}/sessions", response_model=schemas.SessionOut)
def create_session(project_id: int, payload: schemas.SessionCreate, db: DBSession = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    session = models.SurveySession(project_id=project_id, **payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    out = schemas.SessionOut.model_validate(session).model_dump()
    out["reading_count"] = 0
    return out


@app.get("/api/projects/{project_id}/sessions", response_model=List[schemas.SessionOut])
def list_sessions(project_id: int, db: DBSession = Depends(get_db)):
    sessions = (
        db.query(models.SurveySession)
        .filter(models.SurveySession.project_id == project_id)
        .order_by(models.SurveySession.survey_date)
        .all()
    )
    out = []
    for s in sessions:
        d = schemas.SessionOut.model_validate(s).model_dump()
        d["reading_count"] = len(s.readings)
        d["has_photo"] = bool(s.photo_filename)
        out.append(d)
    return out


@app.delete("/api/sessions/{session_id}")
def delete_session(session_id: int, db: DBSession = Depends(get_db)):
    session = db.get(models.SurveySession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.photo_filename:
        _delete_photo_file(session_id, session.photo_filename)
    db.delete(session)
    db.commit()
    return {"ok": True}


def _session_photo_dir(session_id: int) -> str:
    d = os.path.join(UPLOADS_DIR, str(session_id))
    os.makedirs(d, exist_ok=True)
    return d


def _delete_photo_file(session_id: int, filename: str):
    path = os.path.join(UPLOADS_DIR, str(session_id), filename)
    if os.path.exists(path):
        os.remove(path)


ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}


@app.post("/api/sessions/{session_id}/photo", response_model=schemas.SessionOut)
async def upload_session_photo(session_id: int, file: UploadFile = File(...), db: DBSession = Depends(get_db)):
    session = db.get(models.SurveySession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(400, f"Unsupported image type '{ext}'. Use JPG, PNG, WEBP, or HEIC.")

    content = await file.read()
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(400, "Photo is larger than 15MB — please use a smaller image.")

    if session.photo_filename:
        _delete_photo_file(session_id, session.photo_filename)

    filename = f"slab{ext}"
    with open(os.path.join(_session_photo_dir(session_id), filename), "wb") as f:
        f.write(content)

    session.photo_filename = filename
    db.commit()
    db.refresh(session)

    out = schemas.SessionOut.model_validate(session).model_dump()
    out["reading_count"] = len(session.readings)
    out["has_photo"] = True
    return out


@app.get("/api/sessions/{session_id}/photo")
def get_session_photo(session_id: int, db: DBSession = Depends(get_db)):
    session = db.get(models.SurveySession, session_id)
    if not session or not session.photo_filename:
        raise HTTPException(404, "No photo uploaded for this session")
    path = os.path.join(UPLOADS_DIR, str(session_id), session.photo_filename)
    if not os.path.exists(path):
        raise HTTPException(404, "Photo file missing on disk")
    return FileResponse(path)


@app.delete("/api/sessions/{session_id}/photo")
def delete_session_photo(session_id: int, db: DBSession = Depends(get_db)):
    session = db.get(models.SurveySession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.photo_filename:
        _delete_photo_file(session_id, session.photo_filename)
        session.photo_filename = None
        db.commit()
    return {"ok": True}


def _get_session_or_404(db: DBSession, session_id: int) -> models.SurveySession:
    session = (
        db.query(models.SurveySession)
        .options(joinedload(models.SurveySession.readings).joinedload(models.Reading.grid_point))
        .get(session_id)
    )
    if not session:
        raise HTTPException(404, "Session not found")
    return session


def _reading_out(r: models.Reading) -> dict:
    return {
        "id": r.id,
        "grid_point_id": r.grid_point_id,
        "row_label": r.grid_point.row_label,
        "col_label": r.grid_point.col_label,
        "x_mm": r.grid_point.x_mm,
        "y_mm": r.grid_point.y_mm,
        "value_mv": r.value_mv,
        "reading_1": r.reading_1,
        "reading_2": r.reading_2,
        "reading_3": r.reading_3,
        "resistivity_kohm_cm": r.resistivity_kohm_cm,
        "flagged": r.flagged,
        "flag_reason": r.flag_reason,
        "description": r.description,
    }


@app.get("/api/sessions/{session_id}/readings", response_model=List[schemas.ReadingOut])
def get_readings(session_id: int, db: DBSession = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    return [_reading_out(r) for r in session.readings]


@app.put("/api/sessions/{session_id}/readings", response_model=List[schemas.ReadingOut])
def set_readings(session_id: int, payload: schemas.ReadingsBulkIn, db: DBSession = Depends(get_db)):
    """Upsert readings for a session — used by the manual-entry grid."""
    session = db.get(models.SurveySession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    project_point_ids = {gp.id for gp in session.project.grid_points}

    for item in payload.readings:
        if item.grid_point_id not in project_point_ids:
            raise HTTPException(400, f"grid_point_id {item.grid_point_id} does not belong to this project")

        resolved, flagged, reason = validation.resolve_value_and_flag(
            item.reading_1, item.reading_2, item.reading_3, item.value_mv
        )
        if resolved is None:
            continue  # nothing to store for this point yet (blank cell)

        existing = (
            db.query(models.Reading)
            .filter_by(session_id=session_id, grid_point_id=item.grid_point_id)
            .first()
        )
        if existing:
            existing.value_mv = resolved
            existing.reading_1 = item.reading_1
            existing.reading_2 = item.reading_2
            existing.reading_3 = item.reading_3
            existing.resistivity_kohm_cm = item.resistivity_kohm_cm
            existing.flagged = flagged
            existing.flag_reason = reason
        else:
            db.add(models.Reading(
                session_id=session_id,
                grid_point_id=item.grid_point_id,
                value_mv=resolved,
                reading_1=item.reading_1,
                reading_2=item.reading_2,
                reading_3=item.reading_3,
                resistivity_kohm_cm=item.resistivity_kohm_cm,
                flagged=flagged,
                flag_reason=reason,
            ))
    db.commit()

    session = _get_session_or_404(db, session_id)
    return [_reading_out(r) for r in session.readings]


@app.patch("/api/sessions/{session_id}/points/{grid_point_id}/description", response_model=schemas.ReadingOut)
def set_point_description(
    session_id: int, grid_point_id: int, payload: schemas.DescriptionUpdate, db: DBSession = Depends(get_db)
):
    """
    Sets or clears a field note on one point, for this specific session.
    Deliberately separate from the bulk readings PUT: annotating a point
    is an ad-hoc action taken by clicking it on the contour map, not part
    of re-submitting the whole grid's values.
    """
    reading = (
        db.query(models.Reading)
        .filter_by(session_id=session_id, grid_point_id=grid_point_id)
        .first()
    )
    if not reading:
        raise HTTPException(
            404,
            "No reading recorded for this point in this session yet — enter a value before adding a note.",
        )
    reading.description = payload.description or None
    db.commit()
    db.refresh(reading)
    return _reading_out(reading)


@app.post("/api/sessions/{session_id}/upload", response_model=List[schemas.ReadingOut])
async def upload_readings(session_id: int, file: UploadFile = File(...), db: DBSession = Depends(get_db)):
    session = db.get(models.SurveySession, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    content = await file.read()
    try:
        rows = parser.parse_upload(file.filename, content)
    except ValueError as e:
        raise HTTPException(400, str(e))

    label_lookup = {
        (gp.row_label.strip().lower(), gp.col_label.strip().lower()): gp
        for gp in session.project.grid_points
    }

    unmatched = []
    for row in rows:
        key = (row["row_label"].lower(), row["col_label"].lower())
        gp = label_lookup.get(key)
        if not gp:
            unmatched.append(f"{row['col_label']}{row['row_label']}")
            continue

        resolved, flagged, reason = validation.resolve_value_and_flag(
            row["reading_1"], row["reading_2"], row["reading_3"], row["value_mv"]
        )
        if resolved is None:
            continue

        existing = (
            db.query(models.Reading)
            .filter_by(session_id=session_id, grid_point_id=gp.id)
            .first()
        )
        if existing:
            existing.value_mv = resolved
            existing.reading_1 = row["reading_1"]
            existing.reading_2 = row["reading_2"]
            existing.reading_3 = row["reading_3"]
            existing.resistivity_kohm_cm = row["resistivity_kohm_cm"]
            existing.flagged = flagged
            existing.flag_reason = reason
        else:
            db.add(models.Reading(
                session_id=session_id,
                grid_point_id=gp.id,
                value_mv=resolved,
                reading_1=row["reading_1"],
                reading_2=row["reading_2"],
                reading_3=row["reading_3"],
                resistivity_kohm_cm=row["resistivity_kohm_cm"],
                flagged=flagged,
                flag_reason=reason,
            ))
    db.commit()

    if unmatched:
        raise HTTPException(
            400,
            f"Uploaded, but {len(unmatched)} row(s) did not match any grid point "
            f"(check row_label/col_label spelling): {', '.join(unmatched[:10])}"
            + (" ..." if len(unmatched) > 10 else ""),
        )

    session = _get_session_or_404(db, session_id)
    return [_reading_out(r) for r in session.readings]


@app.get("/api/sessions/{session_id}/validate", response_model=schemas.ValidationResult)
def validate_session_endpoint(session_id: int, db: DBSession = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    result = validation.validate_session(db, session.project, session)
    return result


@app.get("/api/sessions/{session_id}/contour", response_model=schemas.ContourResult)
def get_contour(session_id: int, db: DBSession = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    project = session.project

    if not session.readings:
        raise HTTPException(400, "No readings recorded for this session yet")

    points_xy = [(r.grid_point.x_mm, r.grid_point.y_mm) for r in session.readings]
    values = [r.value_mv for r in session.readings]

    x_range = (0, (project.grid_cols - 1) * project.grid_pitch_x_mm)
    y_range = (0, (project.grid_rows - 1) * project.grid_pitch_y_mm)

    xi, yi, zi, method = interpolation.interpolate_surface(points_xy, values, x_range, y_range)
    rebar_x, rebar_y = grid.rebar_overlay_lines(
        project.rebar_rows, project.rebar_cols, project.rebar_pitch_mm,
        project.grid_rows, project.grid_cols, project.grid_pitch_x_mm, project.grid_pitch_y_mm,
    )

    return {
        "x_mm": xi,
        "y_mm": yi,
        "z_mv": zi,
        "method": method,
        "points": [_reading_out(r) for r in session.readings],
        "rebar_x_mm": rebar_x,
        "rebar_y_mm": rebar_y,
    }


@app.get("/api/sessions/{session_id}/stats", response_model=schemas.StatsSummary)
def get_stats(session_id: int, db: DBSession = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    values = [r.value_mv for r in session.readings]
    stats = interpolation.summary_stats(values)

    counts = {"low_risk": 0, "uncertain": 0, "high_risk": 0}
    for v in values:
        counts[interpolation.classify_astm(v)] += 1

    stats["classification"] = counts
    return stats


@app.get("/api/sessions/{session_id}/export")
def export_readings(session_id: int, db: DBSession = Depends(get_db)):
    """
    Exports readings as a round-trip-ready .xlsx: Sheet 1 is the exact
    minimal shape the upload parser expects (row_label, col_label, value_mv,
    ...), and nothing else — so downloading this file and re-uploading it
    later (into this project or a new one with the same grid) just works.
    Sheets 2-3 add human-readable context (project config, coordinates,
    risk tier) that the parser ignores, since it only reads the first sheet.
    """
    session = _get_session_or_404(db, session_id)
    project = session.project

    header_fill = PatternFill("solid", fgColor="EDEBE3")
    header_font = Font(bold=True, size=10)
    thin = Side(style="thin", color="B8B2A0")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal="center", vertical="center")

    def _write_header(ws, headers):
        for i, h in enumerate(headers, start=1):
            c = ws.cell(row=1, column=i, value=h)
            c.font, c.fill, c.alignment, c.border = header_font, header_fill, center, border
            ws.column_dimensions[get_column_letter(i)].width = max(12, len(h) + 2)
        ws.freeze_panes = "A2"

    wb = Workbook()

    # ---- Sheet 1: Readings — the exact re-upload format, nothing extra ----
    ws = wb.active
    ws.title = "Readings"
    _write_header(ws, ["row_label", "col_label", "value_mv", "reading_1", "reading_2", "reading_3", "resistivity_kohm_cm"])
    for r_idx, r in enumerate(session.readings, start=2):
        for c_idx, v in enumerate([
            r.grid_point.row_label, r.grid_point.col_label, r.value_mv,
            r.reading_1, r.reading_2, r.reading_3, r.resistivity_kohm_cm,
        ], start=1):
            cell = ws.cell(row=r_idx, column=c_idx, value=v)
            cell.border, cell.alignment = border, center

    # ---- Sheet 2: Project Info (reference only) ----
    info = wb.create_sheet("Project Info")
    info.column_dimensions["A"].width = 22
    info.column_dimensions["B"].width = 50
    info_rows = [
        ("Project", project.name),
        ("Description", project.description or "—"),
        ("Slab dimensions", f"{project.slab_width_mm or '—'} × {project.slab_height_mm or '—'} mm"),
        ("Reinforcement layout", f"{project.rebar_rows}×{project.rebar_cols} rods @ {project.rebar_pitch_mm}mm pitch"),
        ("Rod diameter", f"{project.rebar_diameter_mm or '—'} mm"),
        ("Cover depth", f"{project.cover_depth_mm or '—'} mm"),
        ("Reference electrode", project.reference_electrode),
        ("Measurement grid", f"{project.grid_rows}×{project.grid_cols} bounding grid @ "
                              f"{project.grid_pitch_x_mm}×{project.grid_pitch_y_mm}mm pitch"),
        ("Active points", str(len(project.grid_points))),
        ("Session date", str(session.survey_date)),
        ("Session day number", str(session.day_number) if session.day_number is not None else "—"),
        ("Session label", session.label or "—"),
        ("Exported", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
    ]
    for i, (label, value) in enumerate(info_rows, start=1):
        info.cell(row=i, column=1, value=label).font = header_font
        info.cell(row=i, column=2, value=value)

    # ---- Sheet 3: Reference — coordinates + risk tier, for human inspection ----
    ref = wb.create_sheet("Reference (coords + risk)")
    _write_header(ref, ["row_label", "col_label", "x_mm", "y_mm", "value_mv", "risk_tier"])
    for r_idx, r in enumerate(session.readings, start=2):
        for c_idx, v in enumerate([
            r.grid_point.row_label, r.grid_point.col_label, r.grid_point.x_mm, r.grid_point.y_mm,
            r.value_mv, interpolation.classify_astm(r.value_mv),
        ], start=1):
            cell = ref.cell(row=r_idx, column=c_idx, value=v)
            cell.border, cell.alignment = border, center

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    safe_name = "".join(c if c.isalnum() else "_" for c in project.name)
    label = f"day{session.day_number}" if session.day_number is not None else str(session.survey_date)
    filename = f"{safe_name}_{label}_readings.xlsx"
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@app.post("/api/sessions/{session_id}/report")
def generate_report(session_id: int, payload: schemas.ReportRequest, db: DBSession = Depends(get_db)):
    session = _get_session_or_404(db, session_id)
    project = session.project

    if not session.readings:
        raise HTTPException(400, "No readings recorded for this session yet")

    tiers = [t.model_dump() for t in payload.tiers]
    if len(tiers) < 2:
        raise HTTPException(400, "At least 2 tiers are required")

    points_xy = [(r.grid_point.x_mm, r.grid_point.y_mm) for r in session.readings]
    values = [r.value_mv for r in session.readings]
    x_range = (0, (project.grid_cols - 1) * project.grid_pitch_x_mm)
    y_range = (0, (project.grid_rows - 1) * project.grid_pitch_y_mm)
    xi, yi, zi, _method = interpolation.interpolate_surface(points_xy, values, x_range, y_range)
    rebar_x, rebar_y = grid.rebar_overlay_lines(
        project.rebar_rows, project.rebar_cols, project.rebar_pitch_mm,
        project.grid_rows, project.grid_cols, project.grid_pitch_x_mm, project.grid_pitch_y_mm,
    )

    points_for_chart = [
        {"x_mm": r.grid_point.x_mm, "y_mm": r.grid_point.y_mm, "value_mv": r.value_mv}
        for r in session.readings
    ]

    annotations = [
        {
            "label": f"{r.grid_point.col_label}{r.grid_point.row_label}",
            "x_mm": r.grid_point.x_mm, "y_mm": r.grid_point.y_mm,
            "value_mv": r.value_mv, "description": r.description,
        }
        for r in session.readings if r.description
    ]

    stats = interpolation.summary_stats(values)
    tier_counts = {t["id"]: 0 for t in tiers}
    for v in values:
        tier_counts[report.classify_tier(v, tiers)["id"]] += 1

    contour_png = report.render_contour_png(xi, yi, zi, rebar_x, rebar_y, points_for_chart, tiers, annotations)

    photo_bytes = None
    if session.photo_filename:
        photo_path = os.path.join(UPLOADS_DIR, str(session_id), session.photo_filename)
        if os.path.exists(photo_path):
            with open(photo_path, "rb") as f:
                photo_bytes = f.read()

    project_dict = schemas.ProjectOut.model_validate(project).model_dump()
    session_dict = schemas.SessionOut.model_validate(session).model_dump()

    pdf_bytes = report.build_report_pdf(
        project_dict, session_dict, stats, tiers, tier_counts, contour_png, photo_bytes, annotations
    )

    safe_name = "".join(c if c.isalnum() else "_" for c in project.name)
    filename = f"{safe_name}_session{session_id}_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/api/projects/{project_id}/comparison-report")
def generate_comparison_report(project_id: int, payload: schemas.ComparisonReportRequest, db: DBSession = Depends(get_db)):
    project = db.get(models.Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")

    tiers = [t.model_dump() for t in payload.tiers]
    if len(tiers) < 2:
        raise HTTPException(400, "At least 2 tiers are required")

    query = (
        db.query(models.SurveySession)
        .options(joinedload(models.SurveySession.readings).joinedload(models.Reading.grid_point))
        .filter(models.SurveySession.project_id == project_id)
    )
    if payload.session_ids:
        query = query.filter(models.SurveySession.id.in_(payload.session_ids))
    sessions = sorted(query.all(), key=lambda s: (s.survey_date, s.id))

    sessions_with_data = [s for s in sessions if s.readings]
    if len(sessions_with_data) < 2:
        raise HTTPException(
            400,
            "Need at least 2 sessions with readings to build a comparison report "
            f"(found {len(sessions_with_data)}).",
        )

    rebar_x, rebar_y = grid.rebar_overlay_lines(
        project.rebar_rows, project.rebar_cols, project.rebar_pitch_mm,
        project.grid_rows, project.grid_cols, project.grid_pitch_x_mm, project.grid_pitch_y_mm,
    )
    x_range = (0, (project.grid_cols - 1) * project.grid_pitch_x_mm)
    y_range = (0, (project.grid_rows - 1) * project.grid_pitch_y_mm)

    sessions_summary = []
    for s in sessions_with_data:
        points_xy = [(r.grid_point.x_mm, r.grid_point.y_mm) for r in s.readings]
        values = [r.value_mv for r in s.readings]
        xi, yi, zi, _method = interpolation.interpolate_surface(points_xy, values, x_range, y_range)
        points_for_chart = [
            {"x_mm": r.grid_point.x_mm, "y_mm": r.grid_point.y_mm, "value_mv": r.value_mv}
            for r in s.readings
        ]
        contour_png = report.render_mini_contour_png(xi, yi, zi, rebar_x, rebar_y, points_for_chart, tiers)

        stats = interpolation.summary_stats(values)
        tier_counts = {t["id"]: 0 for t in tiers}
        for v in values:
            tier_counts[report.classify_tier(v, tiers)["id"]] += 1
        x_label = f"Day {s.day_number}" if s.day_number is not None else str(s.survey_date)
        photo_bytes = None
        if payload.include_photos and s.photo_filename:
            photo_path = os.path.join(UPLOADS_DIR, str(s.id), s.photo_filename)
            if os.path.exists(photo_path):
                with open(photo_path, "rb") as f:
                    photo_bytes = f.read()
        sessions_summary.append({
            "session_id": s.id,
            "x_label": x_label, "survey_date": str(s.survey_date), "day_number": s.day_number,
            "label": s.label,
            "mean_mv": stats["mean_mv"], "std_mv": stats["std_mv"],
            "min_mv": stats["min_mv"], "max_mv": stats["max_mv"],
            "count": stats["count"], "tier_counts": tier_counts,
            "contour_png_bytes": contour_png,
            "photo_bytes": photo_bytes,
        })

    # Per-point time series: every grid point that has at least one reading
    # across the selected sessions, in row/col order, one column per session.
    point_labels = {}
    for s in sessions_with_data:
        for r in s.readings:
            key = (r.grid_point.row_index, r.grid_point.col_index)
            point_labels[key] = f"{r.grid_point.col_label}{r.grid_point.row_label}"

    columns = [s["x_label"] for s in sessions_summary]
    rows = []
    for key in sorted(point_labels.keys()):
        values_by_session = []
        for s in sessions_with_data:
            match = next(
                (r.value_mv for r in s.readings
                 if (r.grid_point.row_index, r.grid_point.col_index) == key), None
            )
            values_by_session.append(match)
        rows.append({"point": point_labels[key], "values": values_by_session})
    points_timeseries = {"columns": columns, "rows": rows}

    trend_chart_png = report.render_trend_chart_png(sessions_summary, tiers)

    project_dict = schemas.ProjectOut.model_validate(project).model_dump()
    pdf_bytes = report.build_comparison_report_pdf(
        project_dict, sessions_summary, tiers, points_timeseries, trend_chart_png,
        include_photos=payload.include_photos,
    )

    safe_name = "".join(c if c.isalnum() else "_" for c in project.name)
    filename = f"{safe_name}_comparison_report.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
