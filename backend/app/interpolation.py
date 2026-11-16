"""
Spatial interpolation + corrosion-risk classification.

classify_astm() is deliberately isolated from everything else: it takes a
single HCP value in and returns a risk tier out. When concrete resistivity
is added (Phase 2), this becomes classify_combined(hcp, resistivity) using
the Sadowski (2013) Table 6 method, and nothing upstream (grid generation,
interpolation, the API contract for readings) needs to change — only the
function that turns numbers into a tier.
"""
import numpy as np
from scipy.interpolate import griddata

# ASTM C876 thresholds for a Cu/CuSO4 (CSE) reference electrode.
ASTM_HIGH_RISK = -350.0   # < this -> greater than 90% probability of corrosion
ASTM_LOW_RISK = -200.0    # > this -> 90% probability of no corrosion


def classify_astm(value_mv: float) -> str:
    if value_mv < ASTM_HIGH_RISK:
        return "high_risk"
    if value_mv > ASTM_LOW_RISK:
        return "low_risk"
    return "uncertain"


def interpolate_surface(points_xy, values, x_range, y_range, resolution=60):
    """
    points_xy: list of (x_mm, y_mm)
    values: list of float, same length/order as points_xy
    x_range, y_range: (min, max) tuples in mm, defines the mesh extent
    resolution: number of samples along the longer axis

    Returns (x_coords, y_coords, Z) where Z has shape (len(y_coords), len(x_coords)),
    plus the method actually used (cubic falls back to linear/nearest for sparse data).
    """
    pts = np.array(points_xy, dtype=float)
    vals = np.array(values, dtype=float)

    x_min, x_max = x_range
    y_min, y_max = y_range
    # guard against a degenerate (zero-width) axis
    if x_max == x_min:
        x_max = x_min + 1.0
    if y_max == y_min:
        y_max = y_min + 1.0

    aspect = (x_max - x_min) / (y_max - y_min)
    nx = max(int(resolution * max(aspect, 1)), 20)
    ny = max(int(resolution * max(1 / aspect, 1)), 20)

    xi = np.linspace(x_min, x_max, nx)
    yi = np.linspace(y_min, y_max, ny)
    Xi, Yi = np.meshgrid(xi, yi)

    method = "cubic"
    n_unique = len(set(map(tuple, pts)))
    if n_unique < 4:
        method = "nearest"
    else:
        try:
            Zi = griddata(pts, vals, (Xi, Yi), method="cubic")
            if np.isnan(Zi).all():
                raise ValueError("cubic produced no valid values")
        except Exception:
            method = "linear"

    if method != "cubic":
        Zi = griddata(pts, vals, (Xi, Yi), method=method)

    # Fill any remaining NaNs (edges cubic/linear can't reach) with nearest-neighbor.
    if np.isnan(Zi).any():
        Zi_nearest = griddata(pts, vals, (Xi, Yi), method="nearest")
        Zi = np.where(np.isnan(Zi), Zi_nearest, Zi)

    return xi.tolist(), yi.tolist(), Zi.tolist(), method


def summary_stats(values):
    if not values:
        return {"count": 0, "mean_mv": None, "std_mv": None, "min_mv": None, "max_mv": None}
    arr = np.array(values, dtype=float)
    # Sample standard deviation (ddof=1), matching standard reporting convention
    # for a measured sample rather than a full population.
    std = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
    return {
        "count": int(arr.size),
        "mean_mv": round(float(arr.mean()), 2),
        "std_mv": round(std, 2),
        "min_mv": round(float(arr.min()), 2),
        "max_mv": round(float(arr.max()), 2),
    }
