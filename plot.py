# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///

from pathlib import Path
import calendar
import datetime as dt
import json
import math

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np

HERE = Path(__file__).parent
DATA = HERE / "data" / "solar_pulse_2000_2025_raw.json"
OUT_DIR = HERE / "out"

START_YEAR = 2000
END_YEAR = 2025

# Reference-image palette: deep violet -> magenta -> red -> orange -> yellow.
SUN_COLOURS = [
    "#25106A",
    "#5C1AA8",
    "#B51F7D",
    "#EC4E55",
    "#FF8B20",
    "#FFD42A",
    "#FFF3A5",
]
SUN_CMAP = LinearSegmentedColormap.from_list("sun_pulse", SUN_COLOURS)

BACKGROUND = "#07151C"
CORE_BACKGROUND = "#030D18"
CORE_RING = "#6B35B5"
TEXT = "#F2F1EC"
MUTED = "#AEB5BA"

INNER_RADIUS = 1.0
MAX_BAR_LENGTH = 4.2
RADIATION_MAX = 8.0


def load_raw(path: Path) -> dict:
    """Read the committed NASA POWER raw JSON."""
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Run `uv run fetch.py` first."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def group_by_year(payload: dict) -> dict[int, list[tuple[dt.date, float, float]]]:
    """Turn NASA POWER parameter dictionaries into one list per year."""
    params = payload["properties"]["parameter"]
    actual = params["ALLSKY_SFC_SW_DWN"]
    clear = params.get("CLRSKY_SFC_SW_DWN", {})

    years: dict[int, list[tuple[dt.date, float, float]]] = {}

    for key in sorted(actual):
        if not key[:8].isdigit():
            continue

        year = int(key[:4])
        month = int(key[4:6])
        day = int(key[6:8])

        value = float(actual[key])
        clear_value = float(clear.get(key, -999.0))

        if value < 0:
            value = 0.0
        if clear_value < 0:
            clear_value = 0.0

        years.setdefault(year, []).append(
            (dt.date(year, month, day), value, clear_value)
        )

    return years


def colour_for(value: float, scale_max: float):
    """Map a radiation value to the fixed animation colour scale."""
    if scale_max <= 0:
        return SUN_CMAP(0.0)
    return SUN_CMAP(max(0.0, min(value / scale_max, 1.0)))


def month_labels(year: int):
    """Return fixed angle and label positions for the twelve months."""
    labels = []

    for month in range(1, 13):
        theta = 2 * math.pi * (month - 0.5) / 12
        labels.append((theta, calendar.month_abbr[month]))

    return labels


def draw_time_scaffold(ax, total_days: int) -> None:
    """Mark month boundaries and add a quiet, non-data outer corona."""
    outer_radius = INNER_RADIUS + MAX_BAR_LENGTH + 0.12
    reference_year = 2000 if total_days == 366 else 2001
    day_index = 0
    for month in range(12):
        angle = 2 * math.pi * day_index / total_days
        ax.plot(
            [angle, angle],
            [INNER_RADIUS, outer_radius],
            color=TEXT,
            alpha=0.045,
            linewidth=0.5,
            zorder=0,
        )
        day_index += calendar.monthrange(reference_year, month + 1)[1]

    theta = np.linspace(0, 2 * math.pi, 360)
    ax.plot(
        theta,
        np.full_like(theta, outer_radius),
        color="#C9A8FF",
        alpha=0.13,
        linewidth=0.65,
        zorder=2,
    )
    particle_angles = np.linspace(0, 2 * math.pi, 32, endpoint=False)
    ax.scatter(
        particle_angles,
        np.full_like(particle_angles, outer_radius + 0.045),
        s=2.2,
        color="#E4D5FF",
        alpha=0.28,
        linewidths=0,
        zorder=3,
    )


def draw_solar_core(ax, pulse: float = 0.0) -> None:
    """Draw the dark core and its subtly breathing violet ring."""
    theta = np.linspace(0, 2 * math.pi, 360)
    ax.fill(
        theta,
        np.full_like(theta, INNER_RADIUS + 0.08),
        color=CORE_RING,
        alpha=0.055,
        zorder=9,
    )
    ax.fill(
        theta,
        np.full_like(theta, INNER_RADIUS),
        color=CORE_BACKGROUND,
        zorder=10,
    )
    ax.plot(
        theta,
        np.full_like(theta, INNER_RADIUS + 0.035 + 0.055 * pulse),
        color=CORE_RING,
        alpha=0.42 + 0.24 * pulse,
        linewidth=0.85 + 0.25 * pulse,
        zorder=11,
    )


def render_year(
    year: int,
    rows: list[tuple[dt.date, float, float]],
    scale_max: float,
    output_path: Path,
    bar_progress: float = 1.0,
) -> None:
    """Render one year's Solar Pulse, optionally growing the beams from the core."""
    total_days = 366 if calendar.isleap(year) else 365
    bar_progress = max(0.0, min(bar_progress, 1.0))

    fig = plt.figure(figsize=(12, 10), dpi=180, facecolor=BACKGROUND)
    ax = fig.add_axes(
        [0.045, 0.075, 0.67, 0.82],
        projection="polar",
        facecolor=BACKGROUND,
    )

    ax.set_theta_direction(-1)
    ax.set_theta_offset(math.pi / 2)

    width = 2 * math.pi / total_days * 0.92

    values = [value for _, value, _ in rows]
    mean_value = sum(values) / len(values)

    draw_time_scaffold(ax, total_days)

    for index, (date, actual, clear) in enumerate(rows):
        angle = 2 * math.pi * index / total_days
        radius = MAX_BAR_LENGTH * actual / scale_max * bar_progress
        intensity = max(0.0, min(actual / scale_max, 1.0))

        # Actual / clear-sky controls visibility only.
        if clear > 0:
            transparency = max(0.30, min(actual / clear, 1.0))
        else:
            transparency = 0.55

        # Soft layered bloom follows intensity without changing the data encoding.
        if intensity > 0.60:
            bloom_strength = (intensity - 0.60) / 0.40
            ax.bar(
                angle,
                (radius + 0.18 * bar_progress),
                width=width * 2.35,
                bottom=INNER_RADIUS,
                color=colour_for(actual, scale_max),
                alpha=0.018 + bloom_strength * 0.035,
                linewidth=0,
                align="center",
                zorder=1,
            )
            ax.bar(
                angle,
                (radius + 0.08 * bar_progress),
                width=width * 1.55,
                bottom=INNER_RADIUS,
                color=colour_for(actual, scale_max),
                alpha=0.025 + bloom_strength * 0.075,
                linewidth=0,
                align="center",
                zorder=2,
            )

        ax.bar(
            angle,
            radius,
            width=width,
            bottom=INNER_RADIUS,
            color=colour_for(actual, scale_max),
            alpha=transparency,
            linewidth=0,
            align="center",
        )

    ax.set_ylim(0, INNER_RADIUS + MAX_BAR_LENGTH + 0.45)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.spines["polar"].set_visible(False)

    draw_solar_core(ax)

    ax.text(
        0,
        0,
        f"{year}",
        color=TEXT,
        fontsize=18,
        ha="center",
        va="center",
        zorder=12,
    )

    # Month labels.
    for theta_value, label in month_labels(year):
        ax.text(
            theta_value,
            INNER_RADIUS + MAX_BAR_LENGTH + 0.28,
            label,
            color=TEXT,
            fontsize=10,
            ha="center",
            va="center",
        )

    # Title.
    fig.text(
        0.045,
        0.955,
        "Solar Pulse — Hong Kong",
        color=TEXT,
        fontsize=25,
        ha="left",
        va="top",
    )

    fig.text(
        0.045,
        0.915,
        f"{year}  ·  annual frame",
        color=MUTED,
        fontsize=10,
        ha="left",
        va="top",
    )

    # Compact poster-style information panel.
    fig.text(
        0.745,
        0.76,
        "SOLAR RADIATION",
        color=TEXT,
        fontsize=11,
        va="top",
    )
    legend_ax = fig.add_axes([0.745, 0.685, 0.20, 0.022])
    gradient = np.linspace(0, scale_max, 256)[None, :]
    legend_ax.imshow(
        gradient,
        aspect="auto",
        cmap=SUN_CMAP,
        extent=[0, scale_max, 0, 1],
    )
    legend_ax.set_yticks([])
    tick_values = np.linspace(0, scale_max, 5)
    legend_ax.set_xticks(tick_values)
    legend_ax.set_xticklabels(
        [f"{value:.1f}" for value in tick_values],
        color=TEXT,
        fontsize=7,
    )
    legend_ax.tick_params(axis="x", colors=TEXT, length=2, pad=2)
    for spine in legend_ax.spines.values():
        spine.set_visible(False)
    fig.text(0.745, 0.55, "NASA POWER\nHong Kong · 2000–2025",
             color=MUTED, fontsize=9, va="top", linespacing=1.5)
    fig.text(0.745, 0.39, f"{year}", color=TEXT, fontsize=24, va="top")
    fig.text(
        0.745,
        0.32,
        f"Mean  {mean_value:.2f} kWh/m²/day\n"
        f"Peak   {max(values):.2f} kWh/m²/day",
        color=MUTED,
        fontsize=8.5,
        va="top",
        linespacing=1.7,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        dpi=180,
        bbox_inches="tight",
        facecolor=BACKGROUND,
    )
    plt.close(fig)


def main() -> None:
    payload = load_raw(DATA)
    years = group_by_year(payload)

    missing = [
        year for year in range(START_YEAR, END_YEAR + 1)
        if year not in years
    ]
    if missing:
        raise ValueError(f"Missing years in raw data: {missing}")

    # Fixed scale across the animation.
    scale_max = RADIATION_MAX

    render_year(
        2025,
        years[2025],
        scale_max,
        OUT_DIR / "solar_pulse_2025.png",
    )

    print(f"Saved {OUT_DIR / 'solar_pulse_2025.png'}")


if __name__ == "__main__":
    main()
