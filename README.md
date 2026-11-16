# HCP Contour Mapper

Automates half-cell potential (HCP) contour map generation for reinforced
concrete corrosion assessment (ASTM C876), built for a civil engineering EDI
project. Replaces manual grid-paper contour drawing with: define a slab once
→ record readings per survey date → get an interpolated, classified contour
map automatically.

**Phase 1 scope:** HCP only. Concrete resistivity and the combined
Type 1/2/3 classification from Sadowski (2013) are deliberately deferred —
see "Extending to Phase 2" below for exactly where that plugs in.

**Deploying so someone else can open it from anywhere:** see [DEPLOYMENT.md](./DEPLOYMENT.md).

## Stack

- **Backend:** FastAPI + SQLAlchemy + SQLite, scipy for spatial interpolation, pandas/openpyxl for bulk import, matplotlib + reportlab for the PDF report
- **Frontend:** React + Vite, Plotly.js for the interactive contour rendering

## Quick start

You need Python 3.10+ and Node 18+.

```bash
# 1. Backend
cd backend
pip install -r requirements.txt
python run.py
# → API running at http://localhost:8000 (docs at /docs)

# 2. Frontend (new terminal)
cd frontend
npm install
npm run dev
# → App running at http://localhost:5173
```

The frontend dev server proxies `/api/*` to `http://localhost:8000`
(see `frontend/vite.config.js`), so both need to be running. For a
production deploy where frontend and backend are on different domains, set
`VITE_API_BASE_URL` — see `frontend/.env.example` and DEPLOYMENT.md.

A sample dataset is included at `sample_data/sample_readings.csv` — it's the
actual Table 3 data from Sadowski (2013), reproduced so you can verify the
pipeline against a published result. Create a project with the defaults
(9×9 grid, 75mm pitch), confirm the grid, create a session, and upload that
CSV. The stats panel should read mean −211.1 mV / std 53.5 mV / min −432 mV /
max −144 mV, matching the paper's Table 5.

## Customizable risk classification

The contour map's color scale is not hardcoded to the plain 3-tier ASTM
C876 bins. It defaults to a 4-tier scheme (Severe / High / Uncertain / Low,
matching the extended CSE classification table with a −500mV "severe"
cutoff below the standard −350mV "high" threshold), and every tier's label,
color, and boundary is editable from the "Color scale settings" panel above
the chart — including adding or removing tiers entirely. The scheme is
shared between the contour map and the stats panel (both read from the same
`tiers` state in `ProjectWorkspace`, defined in `frontend/src/lib/riskTiers.js`)
so they can never disagree about how many points fall in which bucket, and
it's persisted per-project in `localStorage` so a customization survives a
page reload.

## PDF report

"Download report (PDF)" on the analysis tab generates a single-page report —
project configuration, the contour map (re-rendered server-side with
matplotlib using the *same* interpolation and the *same* tier scheme as the
live view), summary statistics, and the risk-tier breakdown. Backend logic
lives in `backend/app/report.py`.

## Field notes on points

On the contour map, click any point to attach a short note (up to 500
characters) — e.g. "visible rust staining", "hairline crack". Notes are
stored per reading (so per point *per survey date*, not per grid point), show
as a black ring on the interactive map, and appear in that session's PDF
report twice: as a labeled, ringed callout on the contour figure and as a row
in a "Field notes" table (point, value, description). Saved via
`PATCH /api/sessions/{id}/points/{grid_point_id}/description`.

## How it's organized

```
backend/app/
  models.py         Project, GridPoint, SurveySession, Reading (SQLAlchemy)
  schemas.py         Pydantic request/response contracts
  grid.py             Coordinate generation + rebar overlay positions
  interpolation.py   scipy interpolation + classify_astm() (plain 3-tier default)
  validation.py       Range checks, missing-point checks, triplicate flagging
  parser.py           CSV/XLSX long-format upload parser
  report.py           PDF report generation (matplotlib figure + reportlab layout)
  main.py             All API routes

frontend/src/
  App.jsx                    Sidebar + project switcher
  lib/
    riskTiers.js              N-tier classification logic (classify, colorscale, add/remove tier)
  components/
    ProjectSetup.jsx         Slab geometry / rebar layout / grid config form
    GridPreview.jsx          Review generated grid, rename axes, confirm
    ProjectWorkspace.jsx     Tabs: sessions/data-entry vs contour/analysis
    SessionManager.jsx       Create/select survey sessions
    DataEntryGrid.jsx        Manual entry table + CSV/XLSX upload
    ValidationPanel.jsx      Missing points, range errors, triplicate warnings
    ContourMap.jsx           Plotly contour + N-tier color scale editor + rebar overlay
    StatsPanel.jsx           Mean/std/min/max + risk-tier counts (from the same tiers state)
    ReportPanel.jsx          Triggers PDF report generation/download
    Loading.jsx              Shared spinner used across loading states
```

## Design decisions worth knowing about

**The measurement grid is independent of the rebar layout.** This mirrors
the actual published methodology (Sadowski 2013): HCP surveys use a uniform
grid over the whole slab (default 75mm pitch), not one tied to rebar
position. Rebar is only used to draw the dashed overlay lines on the contour
— it never constrains where a grid point can be. This is also why you can
resize the grid (e.g. 4×4 → 12×9) without touching any interpolation or
rendering code; `scipy.interpolate` works on arbitrary point clouds.

**Configuration vs. sessions.** A project's geometry (slab size, rebar
layout, grid pitch) is set once and locked in when you confirm the grid.
Everything after that — readings — belongs to a `SurveySession` (one per
survey date), and every session reuses the exact same grid coordinates. This
is what makes day-over-day contour comparison possible, and what a
forecasting feature would build on top of.

**Long-format CSV upload**, not a wide matrix. Every row is one
`(row_label, col_label, value_mv)` reading. This is deliberate: it works
identically regardless of grid size, and it's the same shape the manual
entry grid produces internally, so both input paths converge on one schema.

## Extending to Phase 2 (concrete resistivity)

Two things were built to make this a config change, not a rewrite:

1. `Reading.resistivity_kohm_cm` already exists on the model (nullable).
   No migration needed — just start populating it.
2. `interpolation.classify_astm(value_mv)` is the single function that
   turns a number into a risk tier. Replace/extend it with
   `classify_combined(hcp, resistivity)` using Sadowski's Table 6, and
   nothing upstream (grid generation, interpolation, the API routes, the
   contour renderer) needs to change — the renderer just colors by whatever
   tier comes back.

## Known limitations (by design, for Phase 1)

**Irregular survey layouts are supported.** Not every project's grid is a
full rectangle — a real HCP survey often has points on some row/column
intersections but not others (e.g. an OSWB border with gaps at the corners).
The grid generator always creates the full rectangular bounding box first,
but the grid preview screen lets you click individual points to exclude them
before confirming — they're genuinely deleted, not just hidden, so they never
show up as "missing" in validation. This is only available before any session
exists for the project; once readings have been recorded, the grid shape is
locked (deleting a point after data collection has started would silently
orphan historical readings across sessions) — start a new project if the
layout needs to change after that point.


- Rebar pitch is assumed constant in both directions.
- No auth/multi-user support — this is a single-operator tool for now.
- SQLite by default; swap the `DATABASE_URL` env var for Postgres if this
  needs to run somewhere shared.
