"""
Generates the downloadable analysis reports (PDF).

Split in two halves on purpose: matplotlib renders the actual contour
figure and trend chart (reportlab has no charting capability), reportlab
lays out the surrounding document — title, project metadata, the embedded
figures, and the stats/classification tables. This mirrors the same
interpolation and classification logic used by the live web view
(interpolation.py, riskTiers.js's Python counterpart below), so the PDF
always matches what's on screen rather than being a separately-maintained
rendering path.
"""
import io
import itertools
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")  # headless — no display available on the server
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors as rl_colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def classify_tier(value, tiers):
    """Python mirror of frontend/src/lib/riskTiers.js's classify()."""
    for t in tiers[:-1]:
        if t["boundary"] is not None and value < t["boundary"]:
            return t
    return tiers[-1]


def tier_range_text(tiers, i):
    prev_boundary = tiers[i - 1]["boundary"] if i > 0 else None
    boundary = tiers[i]["boundary"]
    if prev_boundary is None and boundary is not None:
        return f"< {boundary} mV"
    if boundary is None:
        return f"> {prev_boundary} mV"
    return f"{prev_boundary} to {boundary} mV"


def _levels_and_colors(tiers):
    """Same monotonic-clamp guard as buildRiskColorscale() in riskTiers.js —
    a tier keeps its assigned color even if boundaries are briefly out of
    order, rather than matplotlib raising on non-increasing levels."""
    boundaries, prev = [], -1e9
    for t in tiers[:-1]:
        b = max(t["boundary"], prev) if t["boundary"] is not None else prev
        boundaries.append(b)
        prev = b
    levels = [-1e9] + boundaries + [1e9]
    colors = [t["color"] for t in tiers]
    return levels, colors


def render_contour_png(xi, yi, zi, rebar_x, rebar_y, points, tiers, annotations=None, dpi=170):
    levels, colors = _levels_and_colors(tiers)
    X, Y, Z = np.array(xi), np.array(yi), np.array(zi)

    fig, ax = plt.subplots(figsize=(7.2, 6.0), dpi=dpi)
    ax.contourf(X, Y, Z, levels=levels, colors=colors)
    if len(levels) > 2:
        ax.contour(X, Y, Z, levels=levels[1:-1], colors="black", linewidths=0.5, alpha=0.45)

    for x in rebar_x:
        ax.axvline(x, color="#8a8578", linestyle=(0, (3, 2)), linewidth=1)
    for y in rebar_y:
        ax.axhline(y, color="#8a8578", linestyle=(0, (3, 2)), linewidth=1)

    for p in points:
        tier = classify_tier(p["value_mv"], tiers)
        ax.scatter(p["x_mm"], p["y_mm"], color=tier["color"], edgecolors="white",
                   linewidths=0.8, s=42, zorder=5)

    # Points with a field note get a black ring plus a labeled callout, so
    # the "Field notes" table (added below in build_report_pdf) can be tied
    # back to an exact spot on the map, not just a row/column label in text.
    for a in (annotations or []):
        ax.scatter(a["x_mm"], a["y_mm"], facecolors="none", edgecolors="black",
                   linewidths=1.3, s=95, zorder=6)
        ax.annotate(
            a["label"], (a["x_mm"], a["y_mm"]),
            xytext=(8, 8), textcoords="offset points",
            fontsize=7.5, fontweight="bold", color="black", zorder=7,
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="black", linewidth=0.5, alpha=0.9),
        )

    ax.set_xlabel("x (mm)", fontsize=9)
    ax.set_ylabel("y (mm)", fontsize=9)
    ax.tick_params(labelsize=8)
    x_pad = (X.max() - X.min()) * 0.03 or 10
    y_pad = (Y.max() - Y.min()) * 0.03 or 10
    ax.set_xlim(X.min() - x_pad, X.max() + x_pad)
    ax.set_ylim(Y.max() + y_pad, Y.min() - y_pad)  # inverted so row 1 sits at top
    ax.set_aspect("equal")

    handles = [
        Patch(facecolor=t["color"], label=f'{t["label"]} ({tier_range_text(tiers, i)})')
        for i, t in enumerate(tiers)
    ]
    ncol = min(len(tiers), 3)
    # matplotlib's default legend fill is column-major, which reads oddly for
    # a short list — reordering the handles first makes the multi-column
    # layout read in the same left-to-right, top-to-bottom order as tiers.
    ordered = list(itertools.chain(*[handles[i::ncol] for i in range(ncol)]))
    ax.legend(handles=ordered, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=ncol, fontsize=7.5, frameon=False)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def render_mini_contour_png(xi, yi, zi, rebar_x, rebar_y, points, tiers, dpi=160):
    """
    Compact thumbnail contour map for multi-session comparison report.
    Omits heavy legend and bulky text while preserving contour gradients,
    rebar gridlines, and risk-tier point scatter.
    """
    levels, colors = _levels_and_colors(tiers)
    X, Y, Z = np.array(xi), np.array(yi), np.array(zi)

    fig, ax = plt.subplots(figsize=(3.4, 2.7), dpi=dpi)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    ax.contourf(X, Y, Z, levels=levels, colors=colors)
    if len(levels) > 2:
        ax.contour(X, Y, Z, levels=levels[1:-1], colors="black", linewidths=0.4, alpha=0.35)

    for x in rebar_x:
        ax.axvline(x, color="#8a8578", linestyle=(0, (3, 2)), linewidth=0.6, alpha=0.7)
    for y in rebar_y:
        ax.axhline(y, color="#8a8578", linestyle=(0, (3, 2)), linewidth=0.6, alpha=0.7)

    for p in points:
        tier = classify_tier(p["value_mv"], tiers)
        ax.scatter(p["x_mm"], p["y_mm"], color=tier["color"], edgecolors="white",
                   linewidths=0.5, s=18, zorder=5)

    x_pad = (X.max() - X.min()) * 0.03 or 10
    y_pad = (Y.max() - Y.min()) * 0.03 or 10
    ax.set_xlim(X.min() - x_pad, X.max() + x_pad)
    ax.set_ylim(Y.max() + y_pad, Y.min() - y_pad)  # inverted so row 1 sits at top
    ax.set_aspect("equal")

    ax.tick_params(labelsize=6, length=2, pad=1.5)
    for spine in ax.spines.values():
        spine.set_color("#b8b2a0")
        spine.set_linewidth(0.5)

    fig.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()



def build_report_pdf(project, session, stats, tiers, tier_counts, contour_png_bytes, photo_bytes=None, annotations=None):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=15 * mm, leftMargin=18 * mm, rightMargin=18 * mm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], fontSize=18, spaceAfter=2)
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=styles["Normal"],
        textColor=rl_colors.HexColor("#5b5f5a"), fontSize=10, spaceAfter=14,
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=12,
        spaceBefore=10, spaceAfter=6, textColor=rl_colors.HexColor("#1b6e6e"),
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=8, textColor=rl_colors.HexColor("#8a8578"),
    )
    cell_style = ParagraphStyle("Cell", parent=styles["Normal"], fontSize=8.5, leading=11)

    grid_style = TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#d7d2c3")),
    ])

    story = []
    story.append(Paragraph("HCP Corrosion Assessment Report", title_style))
    session_label = f"Day {session['day_number']}" if session.get("day_number") is not None else str(session["survey_date"])
    story.append(Paragraph(f"{project['name']} — {session_label} ({session['survey_date']})", subtitle_style))

    story.append(Paragraph("Project configuration", h2))
    meta_rows = [
        ["Slab dimensions", f"{project.get('slab_width_mm') or '—'} × {project.get('slab_height_mm') or '—'} mm"],
        ["Reinforcement layout",
         f"{project['rebar_rows']}×{project['rebar_cols']} rods @ {project['rebar_pitch_mm']}mm pitch"
         f"{', ' + str(project['rebar_diameter_mm']) + 'mm dia' if project.get('rebar_diameter_mm') else ''}"],
        ["Cover depth", f"{project.get('cover_depth_mm') or '—'} mm"],
        ["Reference electrode", project.get("reference_electrode", "CSE")],
        ["Measurement grid",
         f"{project['grid_rows']}×{project['grid_cols']} bounding grid @ "
         f"{project['grid_pitch_x_mm']}×{project['grid_pitch_y_mm']}mm pitch "
         f"({len(project.get('grid_points', []))} active points)"],
    ]
    meta_table = Table(meta_rows, colWidths=[140, 340])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), rl_colors.HexColor("#5b5f5a")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, rl_colors.HexColor("#d7d2c3")),
    ]))
    story.append(meta_table)

    if photo_bytes:
        story.append(Paragraph("Slab photo", h2))
        photo_img = RLImage(io.BytesIO(photo_bytes))
        max_photo_width = 174 * mm
        max_photo_height = 110 * mm
        aspect = photo_img.imageHeight / photo_img.imageWidth
        w, h = max_photo_width, max_photo_width * aspect
        if h > max_photo_height:
            h = max_photo_height
            w = h / aspect
        photo_img.drawWidth = w
        photo_img.drawHeight = h
        story.append(photo_img)
        story.append(Spacer(1, 8))

    story.append(Paragraph("Contour map", h2))
    img = RLImage(io.BytesIO(contour_png_bytes))
    max_width = 174 * mm
    aspect = img.imageHeight / img.imageWidth
    img.drawWidth = max_width
    img.drawHeight = max_width * aspect
    story.append(img)

    story.append(Paragraph("Summary statistics", h2))
    stat_rows = [
        ["Mean", "Std dev", "Min", "Max", "Points"],
        [f"{stats['mean_mv']} mV", f"{stats['std_mv']} mV", f"{stats['min_mv']} mV",
         f"{stats['max_mv']} mV", str(stats["count"])],
    ]
    stat_table = Table(stat_rows, colWidths=[96] * 5)
    stat_style = TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#f6f4ee")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#d7d2c3")),
    ])
    stat_table.setStyle(stat_style)
    story.append(stat_table)
    story.append(Spacer(1, 10))

    story.append(Paragraph("Risk classification", h2))
    class_rows = [["Tier", "Range", "Points"]]
    for i, t in enumerate(tiers):
        class_rows.append([t["label"], tier_range_text(tiers, i), str(tier_counts.get(t["id"], 0))])
    class_table = Table(class_rows, colWidths=[160, 220, 60])
    class_table.setStyle(grid_style)
    class_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#f6f4ee")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
    ]))
    for i, t in enumerate(tiers, start=1):
        class_table.setStyle(TableStyle([
            ("BACKGROUND", (0, i), (0, i), rl_colors.HexColor(t["color"])),
            ("TEXTCOLOR", (0, i), (0, i), rl_colors.white),
        ]))
    story.append(class_table)

    if annotations:
        story.append(Spacer(1, 10))
        story.append(Paragraph("Field notes", h2))
        note_rows = [["Point", "Value", "Description"]]
        for a in annotations:
            note_rows.append([
                a["label"], f"{a['value_mv']} mV", Paragraph(a["description"], cell_style),
            ])
        note_table = Table(note_rows, colWidths=[50, 60, 330])
        note_table.setStyle(grid_style)
        note_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#f6f4ee")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(note_table)

    story.append(Spacer(1, 16))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story.append(Paragraph(
        f"Generated by HCP Contour Mapper on {generated}. Interpolation method and classification "
        f"thresholds are user-configurable — verify against your department's requirements before "
        f"using this report as a formal deliverable.",
        footer_style,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


# ============================================================================
# Multi-session comparison report
# ============================================================================

def _blend_hex_with_white(hex_color, alpha=0.16):
    """Blends a #rrggbb hex string with white for soft table cell tinting in ReportLab."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        return rl_colors.HexColor("#f6f4ee")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    r_out = int(255 * (1 - alpha) + r * alpha)
    g_out = int(255 * (1 - alpha) + g * alpha)
    b_out = int(255 * (1 - alpha) + b * alpha)
    return rl_colors.Color(r_out / 255.0, g_out / 255.0, b_out / 255.0)


def render_trend_chart_png(sessions_summary, tiers, dpi=200):
    """
    Publication-grade multi-session comparison chart:
    - Horizontal risk-tier background bands & labeled threshold lines
    - Outer Min–Max envelope + inner ±1 Std Dev spread band
    - Bold mean trajectory line with tier-colored markers & value callout pills
    """
    labels = [
        f"{s['x_label']}\n({s['survey_date']})" if s.get("day_number") is not None else s["x_label"]
        for s in sessions_summary
    ]
    means = np.array([float(s["mean_mv"]) for s in sessions_summary])
    stds = np.array([float(s.get("std_mv") or 0.0) for s in sessions_summary])
    mins = np.array([float(s["min_mv"]) for s in sessions_summary])
    maxs = np.array([float(s["max_mv"]) for s in sessions_summary])
    x = np.arange(len(labels))

    fig, ax = plt.subplots(figsize=(8.2, 4.1), dpi=dpi)
    fig.patch.set_facecolor("#faf9f5")
    ax.set_facecolor("#ffffff")

    boundaries = [t["boundary"] for t in tiers[:-1] if t.get("boundary") is not None]
    all_vals = list(mins) + list(maxs) + boundaries
    y_min_raw, y_max_raw = min(all_vals), max(all_vals)
    span = max(y_max_raw - y_min_raw, 80.0)
    y_bottom = y_min_raw - span * 0.14
    y_top = y_max_raw + span * 0.16

    # Soft horizontal background bands for each risk tier
    band_edges = [y_bottom] + sorted(boundaries) + [y_top]
    for i, t in enumerate(tiers):
        if i < len(band_edges) - 1:
            low, high = band_edges[i], band_edges[i + 1]
            if high > low:
                ax.axhspan(low, high, facecolor=t["color"], alpha=0.065, zorder=1)

    ax.grid(True, which="major", axis="both", color="#e6e2d6", linestyle="-", linewidth=0.6, alpha=0.85, zorder=1)

    # Dashed tier boundary lines with right-side pill annotations
    for t in tiers[:-1]:
        b = t.get("boundary")
        if b is not None:
            ax.axhline(b, color=t["color"], linestyle=(0, (5, 3)), linewidth=1.25, alpha=0.85, zorder=2)
            ax.annotate(
                f" {t['label']} (<{b:g} mV) ",
                xy=(1.0, b), xycoords=("axes fraction", "data"),
                xytext=(-6, 4), textcoords="offset points",
                ha="right", va="bottom", fontsize=6.8, fontweight="bold",
                color=t["color"],
                bbox=dict(boxstyle="round,pad=0.18", facecolor="#ffffff", edgecolor=t["color"], linewidth=0.6, alpha=0.92),
                zorder=6,
            )

    # Min-max envelope
    ax.fill_between(x, mins, maxs, color="#1b6e6e", alpha=0.12, zorder=2, label="Min–Max range")
    ax.plot(x, maxs, color="#1b6e6e", linestyle=":", linewidth=0.9, alpha=0.5, zorder=3)
    ax.plot(x, mins, color="#1b6e6e", linestyle=":", linewidth=0.9, alpha=0.5, zorder=3)

    # ±1 Std Dev inner band
    std_low = np.maximum(mins, means - stds)
    std_high = np.minimum(maxs, means + stds)
    ax.fill_between(x, std_low, std_high, color="#1b6e6e", alpha=0.22, zorder=3, label="±1 Std dev spread")

    # Mean trajectory line
    ax.plot(x, means, color="#0f5252", linewidth=2.5, zorder=4, label="Mean HCP")

    # Markers + direct value callouts
    for xi_val, m_val, min_val, max_val in zip(x, means, mins, maxs):
        tier = classify_tier(m_val, tiers)
        ax.scatter(xi_val, m_val, color="white", s=90, zorder=5)
        ax.scatter(xi_val, m_val, color=tier["color"], edgecolors="#0f5252", linewidths=1.2, s=48, zorder=6)

        ax.annotate(
            f"{m_val:.0f} mV",
            (xi_val, m_val),
            xytext=(0, 10), textcoords="offset points",
            ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#1f2421",
            bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#d7d2c3", linewidth=0.7, alpha=0.95),
            zorder=7,
        )
        # Subtle min marker & label at bottom of envelope
        ax.scatter(xi_val, min_val, color="#5b5f5a", s=14, alpha=0.65, zorder=4)
        ax.annotate(
            f"{min_val:.0f}",
            (xi_val, min_val),
            xytext=(0, -10), textcoords="offset points",
            ha="center", va="top", fontsize=6.5, color="#5b5f5a",
            zorder=5,
        )

    ax.set_ylim(y_bottom, y_top)
    ax.set_xlim(-0.35, len(labels) - 0.65 + (0.25 if len(labels) > 2 else 0.15))
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8, fontweight="bold", color="#1f2421")
    ax.set_ylabel("Half-Cell Potential (mV)", fontsize=9, fontweight="bold", color="#1f2421")
    ax.tick_params(axis="y", labelsize=8, colors="#3a3d38")
    ax.tick_params(axis="x", length=4, colors="#8a8578")

    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#b8b2a0")
    ax.spines["bottom"].set_color("#b8b2a0")

    ax.set_title(
        "Mean HCP Progression Over Time  (shaded bands = ±1 SD & Min–Max range)",
        fontsize=10, fontweight="bold", color="#1f2421", pad=12, loc="left",
    )
    ax.legend(
        fontsize=7.5, frameon=True, facecolor="white", edgecolor="#d7d2c3",
        loc="upper right", ncol=3,
    )

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _build_session_contour_card(session_info, tiers, styles, card_width):
    """Builds a compact ReportLab Table card for a single day's contour map + compulsory label + metrics."""
    title_cell_style = ParagraphStyle(
        "ContourCardTitle", parent=styles["Normal"],
        fontSize=8.5, leading=10.5, fontName="Helvetica-Bold", textColor=rl_colors.HexColor("#1f2421"),
    )
    meta_cell_style = ParagraphStyle(
        "ContourCardMeta", parent=styles["Normal"],
        fontSize=7.2, leading=9.5, textColor=rl_colors.HexColor("#5b5f5a"),
    )
    no_contour_style = ParagraphStyle(
        "NoContour", parent=styles["Normal"],
        fontSize=7.5, leading=10, alignment=1, textColor=rl_colors.HexColor("#8a8578"),
    )

    date_str = session_info.get("survey_date", "")
    x_label = session_info.get("x_label", "")
    header_text = f"<b>{x_label}</b> <font color='#5b5f5a' size='7'>({date_str})</font>" if x_label != date_str else f"<b>{x_label}</b>"

    max_img_w = card_width - 8 * mm
    max_img_h = 36 * mm

    contour_flowable = None
    contour_png_bytes = session_info.get("contour_png_bytes")
    if contour_png_bytes:
        try:
            rl_img = RLImage(io.BytesIO(contour_png_bytes))
            aspect = rl_img.imageHeight / float(rl_img.imageWidth or 1)
            w, h = max_img_w, max_img_w * aspect
            if h > max_img_h:
                h = max_img_h
                w = h / aspect
            rl_img.drawWidth = w
            rl_img.drawHeight = h
            contour_flowable = rl_img
        except Exception:
            contour_flowable = None

    if contour_flowable is None:
        placeholder = Table(
            [[Paragraph("Contour map unavailable", no_contour_style)]],
            colWidths=[max_img_w],
            rowHeights=[max_img_h],
        )
        placeholder.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), rl_colors.HexColor("#f2efe6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#d7d2c3")),
        ]))
        contour_flowable = placeholder

    mean_tier = classify_tier(session_info["mean_mv"], tiers)
    tier_hex = mean_tier["color"]
    footer_text = (
        f"<b>Mean:</b> {session_info['mean_mv']} mV &nbsp;|&nbsp; "
        f"<b>Min:</b> {session_info['min_mv']} mV<br/>"
        f"<font color='{tier_hex}'>● {mean_tier['label']}</font>"
    )

    card_table = Table(
        [
            [Paragraph(header_text, title_cell_style)],
            [contour_flowable],
            [Paragraph(footer_text, meta_cell_style)],
        ],
        colWidths=[card_width],
    )
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#f6f4ee")),
        ("BACKGROUND", (0, 1), (-1, 1), rl_colors.white),
        ("BACKGROUND", (0, 2), (-1, 2), rl_colors.HexColor("#faf9f5")),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.6, rl_colors.HexColor("#c9c3b2")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, rl_colors.HexColor("#e2ddd0")),
        ("LINEABOVE", (0, 2), (-1, 2), 0.4, rl_colors.HexColor("#e2ddd0")),
    ]))
    return card_table


def _build_session_photo_card(session_info, tiers, styles, card_width):
    """Builds a compact ReportLab Table card for a single day's slab photo + metrics."""
    title_cell_style = ParagraphStyle(
        "PhotoCardTitle", parent=styles["Normal"],
        fontSize=8.5, leading=10.5, fontName="Helvetica-Bold", textColor=rl_colors.HexColor("#1f2421"),
    )
    meta_cell_style = ParagraphStyle(
        "PhotoCardMeta", parent=styles["Normal"],
        fontSize=7.2, leading=9.5, textColor=rl_colors.HexColor("#5b5f5a"),
    )
    no_photo_style = ParagraphStyle(
        "NoPhoto", parent=styles["Normal"],
        fontSize=7.5, leading=10, alignment=1, textColor=rl_colors.HexColor("#8a8578"),
    )

    date_str = session_info.get("survey_date", "")
    x_label = session_info.get("x_label", "")
    header_text = f"<b>{x_label}</b> <font color='#5b5f5a' size='7'>({date_str})</font>" if x_label != date_str else f"<b>{x_label}</b>"

    max_img_w = card_width - 8 * mm
    max_img_h = 36 * mm

    photo_flowable = None
    photo_bytes = session_info.get("photo_bytes")
    if photo_bytes:
        try:
            rl_img = RLImage(io.BytesIO(photo_bytes))
            aspect = rl_img.imageHeight / float(rl_img.imageWidth or 1)
            w, h = max_img_w, max_img_w * aspect
            if h > max_img_h:
                h = max_img_h
                w = h / aspect
            rl_img.drawWidth = w
            rl_img.drawHeight = h
            photo_flowable = rl_img
        except Exception:
            photo_flowable = None

    if photo_flowable is None:
        placeholder = Table(
            [[Paragraph("No slab photo uploaded<br/>for this session", no_photo_style)]],
            colWidths=[max_img_w],
            rowHeights=[max_img_h],
        )
        placeholder.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), rl_colors.HexColor("#f2efe6")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BOX", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#d7d2c3")),
        ]))
        photo_flowable = placeholder

    mean_tier = classify_tier(session_info["mean_mv"], tiers)
    tier_hex = mean_tier["color"]
    footer_text = (
        f"<b>Mean:</b> {session_info['mean_mv']} mV &nbsp;|&nbsp; "
        f"<b>Min:</b> {session_info['min_mv']} mV<br/>"
        f"<font color='{tier_hex}'>● {mean_tier['label']}</font>"
    )

    card_table = Table(
        [
            [Paragraph(header_text, title_cell_style)],
            [photo_flowable],
            [Paragraph(footer_text, meta_cell_style)],
        ],
        colWidths=[card_width],
    )
    card_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#f6f4ee")),
        ("BACKGROUND", (0, 1), (-1, 1), rl_colors.white),
        ("BACKGROUND", (0, 2), (-1, 2), rl_colors.HexColor("#faf9f5")),
        ("ALIGN", (0, 1), (-1, 1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("BOX", (0, 0), (-1, -1), 0.6, rl_colors.HexColor("#c9c3b2")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, rl_colors.HexColor("#e2ddd0")),
        ("LINEABOVE", (0, 2), (-1, 2), 0.4, rl_colors.HexColor("#e2ddd0")),
    ]))
    return card_table


def build_comparison_report_pdf(project, sessions_summary, tiers, points_timeseries, trend_chart_png, include_photos=False):
    """
    sessions_summary: list of dicts, oldest -> newest, each with
        x_label, survey_date, day_number, mean_mv, std_mv, min_mv, max_mv,
        count, tier_counts (dict keyed by tier id), contour_png_bytes, photo_bytes (optional)
    points_timeseries: {"columns": [x_label, ...], "rows": [{"point": "A1", "values": [v_or_None, ...]}, ...]}
    include_photos: bool, whether to include the daily slab photos comparison section
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=14 * mm, bottomMargin=14 * mm, leftMargin=14 * mm, rightMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    banner_title = ParagraphStyle(
        "BannerTitle", parent=styles["Title"],
        fontSize=16, leading=20, alignment=0, textColor=rl_colors.white, spaceAfter=2,
    )
    banner_sub = ParagraphStyle(
        "BannerSub", parent=styles["Normal"],
        fontSize=9.5, leading=13, textColor=rl_colors.HexColor("#cfe3e2"),
    )
    h2 = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=11.5,
        spaceBefore=11, spaceAfter=5, textColor=rl_colors.HexColor("#14524f"),
    )
    small = ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8.2, leading=11, textColor=rl_colors.HexColor("#5b5f5a"),
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"], fontSize=7.8, textColor=rl_colors.HexColor("#8a8578"),
    )

    story = []

    # Attractive dark-teal header banner
    delta_mean = round(sessions_summary[-1]["mean_mv"] - sessions_summary[0]["mean_mv"], 1)
    delta_sign = "+" if delta_mean > 0 else ""
    header_banner = Table(
        [[
            Paragraph("HCP Session Comparison Report", banner_title),
        ], [
            Paragraph(
                f"<b>{project['name']}</b> — {len(sessions_summary)} sessions compared "
                f"({sessions_summary[0]['x_label']} to {sessions_summary[-1]['x_label']}) &nbsp;·&nbsp; "
                f"Net mean shift: <b>{delta_sign}{delta_mean:g} mV</b>",
                banner_sub,
            ),
        ]],
        colWidths=[182 * mm],
    )
    header_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), rl_colors.HexColor("#164e4e")),
        ("TOPPADDING", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(header_banner)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Trend over time", h2))
    img = RLImage(io.BytesIO(trend_chart_png))
    max_width = 182 * mm
    aspect = img.imageHeight / img.imageWidth
    img.drawWidth = max_width
    img.drawHeight = max_width * aspect
    story.append(img)
    story.append(Spacer(1, 8))

    # Daily Contour Maps Comparison Grid (COMPULSORY - small contour maps of all days + compulsory labels)
    story.append(Paragraph("Daily contour maps comparison", h2))
    story.append(Paragraph(
        "Side-by-side comparison of interpolated corrosion potential contour maps across survey sessions, "
        "paired with each day's compulsory session label, mean, and minimum half-cell potential.",
        small,
    ))
    story.append(Spacer(1, 5))

    cols_per_row = 3
    gap_mm = 3 * mm
    card_w = (182 * mm - gap_mm * (cols_per_row - 1)) / cols_per_row
    contour_cards = [_build_session_contour_card(s, tiers, styles, card_w) for s in sessions_summary]

    grid_rows = []
    for i in range(0, len(contour_cards), cols_per_row):
        chunk = contour_cards[i:i + cols_per_row]
        while len(chunk) < cols_per_row:
            chunk.append("")
        grid_rows.append(chunk)

    contour_grid = Table(grid_rows, colWidths=[card_w + gap_mm / 2] * cols_per_row)
    contour_grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(contour_grid)
    story.append(Spacer(1, 8))

    # Daily Slab Photos Comparison Grid (OPTIONAL - only if user requested slab photos)
    if include_photos:
        story.append(Paragraph("Daily slab photos comparison", h2))
        story.append(Paragraph(
            "Side-by-side visual comparison of uploaded slab photographs across survey sessions.",
            small,
        ))
        story.append(Spacer(1, 5))

        photo_cards = [_build_session_photo_card(s, tiers, styles, card_w) for s in sessions_summary]
        p_grid_rows = []
        for i in range(0, len(photo_cards), cols_per_row):
            chunk = photo_cards[i:i + cols_per_row]
            while len(chunk) < cols_per_row:
                chunk.append("")
            p_grid_rows.append(chunk)

        photo_grid = Table(p_grid_rows, colWidths=[card_w + gap_mm / 2] * cols_per_row)
        photo_grid.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        story.append(photo_grid)
        story.append(Spacer(1, 8))

    story.append(Paragraph("Session summary", h2))
    header = ["Session", "Date", "Mean", "Std dev", "Min", "Max"] + [t["label"] for t in tiers]
    rows = [header]
    for s in sessions_summary:
        row = [
            s["x_label"], s["survey_date"],
            f"{s['mean_mv']} mV", f"{s['std_mv']} mV", f"{s['min_mv']} mV", f"{s['max_mv']} mV",
        ]
        row += [str(s["tier_counts"].get(t["id"], 0)) for t in tiers]
        rows.append(row)
    n_cols = len(header)
    col_width = (182 * mm) / n_cols
    summary_table = Table(rows, colWidths=[col_width] * n_cols, repeatRows=1)
    summary_styles = [
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (5, 0), rl_colors.HexColor("#164e4e")),
        ("TEXTCOLOR", (0, 0), (5, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#d7d2c3")),
    ]
    for r_idx in range(1, len(rows)):
        bg = "#ffffff" if r_idx % 2 == 1 else "#f7f5ef"
        summary_styles.append(("BACKGROUND", (0, r_idx), (-1, r_idx), rl_colors.HexColor(bg)))
    for t_idx, t in enumerate(tiers):
        col_i = 6 + t_idx
        summary_styles.append(("BACKGROUND", (col_i, 0), (col_i, 0), rl_colors.HexColor(t["color"])))
        summary_styles.append(("TEXTCOLOR", (col_i, 0), (col_i, 0), rl_colors.white))
    summary_table.setStyle(TableStyle(summary_styles))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("Reading history by point", h2))
    story.append(Paragraph(
        "Every measured point down the rows and every survey session across the columns, "
        "color-tinted by risk tier to highlight how corrosion progresses at individual grid locations.",
        small,
    ))
    story.append(Spacer(1, 4))
    pt_header = ["Point"] + points_timeseries["columns"]
    pt_rows = [pt_header]
    for r in points_timeseries["rows"]:
        pt_rows.append([r["point"]] + ["—" if v is None else f"{v:g}" for v in r["values"]])
    n_pt_cols = len(pt_header)
    pt_col_width = max((182 * mm) / n_pt_cols, 16 * mm)
    pt_table = Table(pt_rows, colWidths=[pt_col_width] * n_pt_cols, repeatRows=1)
    pt_styles = [
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#164e4e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (0, -1), rl_colors.HexColor("#f6f4ee")),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
        ("GRID", (0, 0), (-1, -1), 0.4, rl_colors.HexColor("#d7d2c3")),
    ]
    for r_idx, r in enumerate(points_timeseries["rows"], start=1):
        for c_idx, v in enumerate(r["values"], start=1):
            if v is not None:
                tier = classify_tier(v, tiers)
                pt_styles.append(("BACKGROUND", (c_idx, r_idx), (c_idx, r_idx), _blend_hex_with_white(tier["color"], 0.16)))
    pt_table.setStyle(TableStyle(pt_styles))
    story.append(pt_table)

    story.append(Spacer(1, 14))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    photo_note = " Daily slab photographs are also included per user selection." if include_photos else " Slab photographs can optionally be included."
    story.append(Paragraph(
        f"Generated by HCP Contour Mapper on {generated}. Daily contour maps with session labels, trend bands, and per-point "
        f"risk classifications are compiled across all recorded sessions for longitudinal comparison.{photo_note}",
        footer_style,
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()

