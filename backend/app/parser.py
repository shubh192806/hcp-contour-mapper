"""
Bulk upload parser.

Accepts a "long format" CSV/XLSX — one row per measurement point — rather
than trying to guess a wide/matrix layout. This is the format-agnostic
choice: it works identically whether the grid is 4x4 or 12x9, and it maps
directly onto (row_label, col_label) which is exactly how points are
addressed everywhere else in the app.

Expected columns (case-insensitive, extra columns are ignored):
    row_label, col_label, value_mv
Optional columns:
    reading_1, reading_2, reading_3, resistivity_kohm_cm

See /sample_data/sample_readings.csv for a working example.
"""
import io
import pandas as pd

REQUIRED_COLUMNS = {"row_label", "col_label"}
OPTIONAL_COLUMNS = ["value_mv", "reading_1", "reading_2", "reading_3", "resistivity_kohm_cm"]


def parse_upload(filename: str, content: bytes) -> list[dict]:
    if filename.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(io.BytesIO(content))
    else:
        df = pd.read_csv(io.BytesIO(content))

    df.columns = [str(c).strip().lower() for c in df.columns]

    missing_cols = REQUIRED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ValueError(
            f"Missing required column(s): {', '.join(sorted(missing_cols))}. "
            f"Expected at least: row_label, col_label, and value_mv (or reading_1/2/3)."
        )
    if "value_mv" not in df.columns and not {"reading_1", "reading_2", "reading_3"} & set(df.columns):
        raise ValueError("Need either a 'value_mv' column or reading_1/reading_2/reading_3 columns.")

    rows = []
    for _, row in df.iterrows():
        row_label = str(row["row_label"]).strip()
        col_label = str(row["col_label"]).strip()
        if row_label in ("", "nan", "None"):
            continue

        def _get(col):
            if col in df.columns and pd.notna(row.get(col)):
                return float(row[col])
            return None

        rows.append({
            "row_label": row_label,
            "col_label": col_label,
            "value_mv": _get("value_mv"),
            "reading_1": _get("reading_1"),
            "reading_2": _get("reading_2"),
            "reading_3": _get("reading_3"),
            "resistivity_kohm_cm": _get("resistivity_kohm_cm"),
        })
    return rows
