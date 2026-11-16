"""
Validation rules for a session's readings, run before interpolation.

Three checks, matching what was scoped in the project chat:
  1. Range check   — HCP values outside a physically plausible window are flagged.
  2. Missing points — every defined grid point should have a reading before
                       interpolation runs; missing points are reported, not
                       silently interpolated through.
  3. Triplicate disagreement — if reading_1/2/3 were supplied, a spread beyond
                       TRIPLICATE_SPREAD_LIMIT_MV usually means bad electrode
                       contact rather than real signal, so it's flagged for
                       the user to review rather than blindly averaged.
"""
from typing import List
from sqlalchemy.orm import Session as DBSession

from . import models

PLAUSIBLE_MIN_MV = -999.0
PLAUSIBLE_MAX_MV = 200.0
TRIPLICATE_SPREAD_LIMIT_MV = 60.0


def resolve_value_and_flag(reading_1, reading_2, reading_3, value_mv):
    """
    Given optional triplicate readings and/or an explicit value, decide the
    representative value_mv to store, plus a flag/reason if the triplicate
    readings disagree with each other.
    """
    triplicate = [v for v in (reading_1, reading_2, reading_3) if v is not None]
    flagged, reason = False, None

    if len(triplicate) >= 2:
        spread = max(triplicate) - min(triplicate)
        if spread > TRIPLICATE_SPREAD_LIMIT_MV:
            flagged = True
            reason = f"Triplicate spread of {spread:.1f} mV exceeds {TRIPLICATE_SPREAD_LIMIT_MV:.0f} mV limit"

    if value_mv is not None:
        resolved = value_mv
    elif triplicate:
        resolved = sum(triplicate) / len(triplicate)
    else:
        resolved = None

    return resolved, flagged, reason


def validate_session(db: DBSession, project: models.Project, session: models.SurveySession) -> dict:
    all_points = {gp.id: gp for gp in project.grid_points}
    readings = {r.grid_point_id: r for r in session.readings}

    issues = []

    missing = [gp for gp_id, gp in all_points.items() if gp_id not in readings]
    for gp in missing:
        issues.append({
            "grid_point_id": gp.id,
            "row_label": gp.row_label,
            "col_label": gp.col_label,
            "severity": "error",
            "message": "No reading recorded for this grid point",
        })

    for r in readings.values():
        gp = all_points.get(r.grid_point_id)
        label = f"{gp.col_label}{gp.row_label}" if gp else str(r.grid_point_id)

        if r.value_mv < PLAUSIBLE_MIN_MV or r.value_mv > PLAUSIBLE_MAX_MV:
            issues.append({
                "grid_point_id": r.grid_point_id,
                "row_label": gp.row_label if gp else None,
                "col_label": gp.col_label if gp else None,
                "severity": "error",
                "message": f"{label}: value {r.value_mv} mV is outside the plausible "
                           f"range [{PLAUSIBLE_MIN_MV}, {PLAUSIBLE_MAX_MV}] mV",
            })

        if r.flagged:
            issues.append({
                "grid_point_id": r.grid_point_id,
                "row_label": gp.row_label if gp else None,
                "col_label": gp.col_label if gp else None,
                "severity": "warning",
                "message": f"{label}: {r.flag_reason}",
            })

    return {
        "ok": len([i for i in issues if i["severity"] == "error"]) == 0,
        "missing_points": len(missing),
        "total_points": len(all_points),
        "issues": issues,
    }
