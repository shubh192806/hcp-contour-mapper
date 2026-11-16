"""
ORM models.

Design principle (see project chat history): configuration is set ONCE per
project (slab geometry, rebar layout, measurement grid), while readings are
captured MANY times, once per SurveySession (one per site visit / survey
date). Every session reuses the exact same GridPoint set, which is what makes
day-over-day contour comparison and future forecasting possible without any
re-parsing or re-alignment.
"""
from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, Float, String, Date, DateTime, ForeignKey, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)

    # Slab geometry (informational, used for report headers + bounding box)
    slab_width_mm = Column(Float, nullable=True)
    slab_height_mm = Column(Float, nullable=True)

    # Reinforcement layout — assumed constant pitch for now (Phase 1).
    rebar_rows = Column(Integer, nullable=False)          # count of bars in the "row" direction
    rebar_cols = Column(Integer, nullable=False)          # count of bars in the "column" direction
    rebar_pitch_mm = Column(Float, nullable=False)        # constant spacing assumption
    rebar_diameter_mm = Column(Float, nullable=True)
    cover_depth_mm = Column(Float, nullable=True)

    # HCP measurement grid — deliberately INDEPENDENT of rebar layout/pitch.
    # This is the grid actually walked during a survey; it may or may not
    # line up with rebar intersections.
    grid_rows = Column(Integer, nullable=False)
    grid_cols = Column(Integer, nullable=False)
    grid_pitch_x_mm = Column(Float, nullable=False)
    grid_pitch_y_mm = Column(Float, nullable=False)

    # Reference electrode, kept explicit because ASTM C876 thresholds assume
    # Cu/CuSO4 (CSE). Other electrodes need different thresholds.
    reference_electrode = Column(String, default="CSE")

    grid_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    grid_points = relationship("GridPoint", back_populates="project", cascade="all, delete-orphan")
    sessions = relationship("SurveySession", back_populates="project", cascade="all, delete-orphan")


class GridPoint(Base):
    __tablename__ = "grid_points"
    __table_args__ = (UniqueConstraint("project_id", "row_index", "col_index", name="uq_grid_point"),)

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    row_index = Column(Integer, nullable=False)   # 0-based, fixed once generated
    col_index = Column(Integer, nullable=False)   # 0-based, fixed once generated
    row_label = Column(String, nullable=False)    # user-editable, e.g. "1".."9" or "13".."16"
    col_label = Column(String, nullable=False)    # user-editable, e.g. "A".."I" or "9".."12"

    x_mm = Column(Float, nullable=False)
    y_mm = Column(Float, nullable=False)

    project = relationship("Project", back_populates="grid_points")
    readings = relationship("Reading", back_populates="grid_point", cascade="all, delete-orphan")


class SurveySession(Base):
    __tablename__ = "survey_sessions"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    day_number = Column(Integer, nullable=True)   # optional, matches "Day 1, Day 5..." convention
    survey_date = Column(Date, default=date.today)
    label = Column(String, nullable=True)         # e.g. "Before NaCl saturation"
    notes = Column(String, nullable=True)

    # Filename of an uploaded slab photo for this survey visit, stored under
    # backend/uploads/sessions/<id>/. Nullable — most sessions won't have one.
    photo_filename = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="sessions")
    readings = relationship("Reading", back_populates="session", cascade="all, delete-orphan")


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (UniqueConstraint("session_id", "grid_point_id", name="uq_reading"),)

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("survey_sessions.id"), nullable=False)
    grid_point_id = Column(Integer, ForeignKey("grid_points.id"), nullable=False)

    value_mv = Column(Float, nullable=False)      # representative HCP value (averaged if triplicate given)

    # Optional raw triplicate, kept for provenance / outlier flagging.
    reading_1 = Column(Float, nullable=True)
    reading_2 = Column(Float, nullable=True)
    reading_3 = Column(Float, nullable=True)

    # Deferred field for Phase 2 (concrete resistivity). Nullable now so no
    # migration is needed when it's wired up later.
    resistivity_kohm_cm = Column(Float, nullable=True)

    flagged = Column(Boolean, default=False)       # set by validation (e.g. triplicate disagreement)
    flag_reason = Column(String, nullable=True)

    # Free-text field note on this specific point, for this specific survey
    # visit (e.g. "visible rust staining", "hairline crack at this location").
    # Tied to the reading rather than the grid point itself since a note is
    # typically about what was observed on that date, not a permanent
    # property of the point.
    description = Column(String, nullable=True)

    session = relationship("SurveySession", back_populates="readings")
    grid_point = relationship("GridPoint", back_populates="readings")
