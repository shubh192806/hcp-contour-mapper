from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ---------- Project ----------

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    slab_width_mm: Optional[float] = None
    slab_height_mm: Optional[float] = None

    rebar_rows: int = Field(ge=2, description="Number of rebars in the row direction")
    rebar_cols: int = Field(ge=2, description="Number of rebars in the column direction")
    rebar_pitch_mm: float = Field(gt=0)
    rebar_diameter_mm: Optional[float] = None
    cover_depth_mm: Optional[float] = None

    grid_rows: int = Field(ge=2, description="Number of measurement grid rows")
    grid_cols: int = Field(ge=2, description="Number of measurement grid columns")
    grid_pitch_x_mm: float = Field(gt=0)
    grid_pitch_y_mm: float = Field(gt=0)

    reference_electrode: str = "CSE"


class GridPointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    row_index: int
    col_index: int
    row_label: str
    col_label: str
    x_mm: float
    y_mm: float


class GridPointRename(BaseModel):
    id: int
    row_label: Optional[str] = None
    col_label: Optional[str] = None


class GridConfirm(BaseModel):
    points: List[GridPointRename] = []
    excluded_point_ids: List[int] = Field(
        default=[],
        description="Grid point IDs to permanently remove — for irregular survey layouts "
                    "where not every row/column intersection was actually measured.",
    )


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: Optional[str] = None
    slab_width_mm: Optional[float] = None
    slab_height_mm: Optional[float] = None
    rebar_rows: int
    rebar_cols: int
    rebar_pitch_mm: float
    rebar_diameter_mm: Optional[float] = None
    cover_depth_mm: Optional[float] = None
    grid_rows: int
    grid_cols: int
    grid_pitch_x_mm: float
    grid_pitch_y_mm: float
    reference_electrode: str
    grid_confirmed: bool
    created_at: datetime
    grid_points: List[GridPointOut] = []


class ProjectSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    grid_rows: int
    grid_cols: int
    grid_confirmed: bool
    created_at: datetime
    session_count: int = 0


# ---------- Session ----------

class SessionCreate(BaseModel):
    day_number: Optional[int] = None
    survey_date: date
    label: Optional[str] = None
    notes: Optional[str] = None


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    day_number: Optional[int] = None
    survey_date: date
    label: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    reading_count: int = 0
    has_photo: bool = False


# ---------- Readings ----------

class ReadingIn(BaseModel):
    grid_point_id: int
    value_mv: Optional[float] = None
    reading_1: Optional[float] = None
    reading_2: Optional[float] = None
    reading_3: Optional[float] = None
    resistivity_kohm_cm: Optional[float] = None
    description: Optional[str] = None


class ReadingsBulkIn(BaseModel):
    readings: List[ReadingIn]


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grid_point_id: int
    row_label: str
    col_label: str
    x_mm: float
    y_mm: float
    value_mv: float
    reading_1: Optional[float] = None
    reading_2: Optional[float] = None
    reading_3: Optional[float] = None
    resistivity_kohm_cm: Optional[float] = None
    flagged: bool
    flag_reason: Optional[str] = None
    description: Optional[str] = None


class DescriptionUpdate(BaseModel):
    description: Optional[str] = Field(default=None, max_length=500)


class ValidationIssue(BaseModel):
    grid_point_id: Optional[int] = None
    row_label: Optional[str] = None
    col_label: Optional[str] = None
    severity: str          # "error" | "warning"
    message: str


class ValidationResult(BaseModel):
    ok: bool
    missing_points: int
    total_points: int
    issues: List[ValidationIssue]


# ---------- Contour / analysis ----------

class ContourResult(BaseModel):
    x_mm: List[float]
    y_mm: List[float]
    z_mv: List[List[float]]          # interpolated grid, shape (len(y_mm), len(x_mm))
    method: str
    points: List[ReadingOut]
    rebar_x_mm: List[float]
    rebar_y_mm: List[float]


class ClassificationCounts(BaseModel):
    low_risk: int = 0       # > -200 mV
    uncertain: int = 0      # -350 to -200 mV
    high_risk: int = 0      # < -350 mV


class StatsSummary(BaseModel):
    count: int
    mean_mv: Optional[float] = None
    std_mv: Optional[float] = None
    min_mv: Optional[float] = None
    max_mv: Optional[float] = None
    classification: ClassificationCounts


# ---------- Report ----------

class TierIn(BaseModel):
    id: str
    label: str
    color: str
    boundary: Optional[float] = None  # null for the last (best/catch-all) tier


class ReportRequest(BaseModel):
    tiers: List[TierIn]


class ComparisonReportRequest(BaseModel):
    tiers: List[TierIn]
    session_ids: Optional[List[int]] = None  # None = every session in the project, oldest to newest
    include_photos: bool = False

