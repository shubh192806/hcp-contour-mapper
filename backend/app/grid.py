"""
Coordinate grid generation.

The measurement grid is generated purely from (grid_rows, grid_cols,
grid_pitch_x_mm, grid_pitch_y_mm) — it does NOT reference the rebar layout.
That decoupling is deliberate: in the reference methodology (Sadowski 2013),
the HCP survey grid is a uniform mesh laid over the whole slab, independent
of where the rebar actually sits. Rebar position is only used later, as an
overlay on the rendered contour.

Default labeling mirrors the published convention: columns get letters
(A, B, C, ...), rows get numbers (1, 2, 3, ...). Either axis can be renamed
per-point after generation (e.g. to match a civil dept's existing bar-ID
convention like "9, 10, 11, 12").
"""
import string


def _col_letters(n: int) -> str:
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA', ... (spreadsheet-style, for grids wider than 26)."""
    letters = ""
    n += 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = string.ascii_uppercase[rem] + letters
    return letters


def generate_grid_points(grid_rows: int, grid_cols: int, pitch_x_mm: float, pitch_y_mm: float):
    """
    Returns a list of dicts: row_index, col_index, row_label, col_label, x_mm, y_mm.
    Origin (0,0) is the top-left corner of the grid.
    """
    points = []
    for r in range(grid_rows):
        for c in range(grid_cols):
            points.append({
                "row_index": r,
                "col_index": c,
                "row_label": str(r + 1),
                "col_label": _col_letters(c),
                "x_mm": round(c * pitch_x_mm, 3),
                "y_mm": round(r * pitch_y_mm, 3),
            })
    return points


def rebar_overlay_lines(rebar_rows: int, rebar_cols: int, rebar_pitch_mm: float,
                         grid_rows: int, grid_cols: int, pitch_x_mm: float, pitch_y_mm: float):
    """
    Compute rebar line positions (in mm) for overlaying on the contour plot.
    Rebar is centered within the measurement grid's bounding box, since the
    two layouts are independently configured and may not share an origin.
    """
    grid_width = (grid_cols - 1) * pitch_x_mm
    grid_height = (grid_rows - 1) * pitch_y_mm
    rebar_width = (rebar_cols - 1) * rebar_pitch_mm
    rebar_height = (rebar_rows - 1) * rebar_pitch_mm

    offset_x = (grid_width - rebar_width) / 2
    offset_y = (grid_height - rebar_height) / 2

    x_lines = [round(offset_x + i * rebar_pitch_mm, 3) for i in range(rebar_cols)]
    y_lines = [round(offset_y + i * rebar_pitch_mm, 3) for i in range(rebar_rows)]
    return x_lines, y_lines
