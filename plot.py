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


def render_year(
    year: int,
    rows: list[tuple[dt.date, float, float]],
    scale_max: float,
    output_path: Path,
) -> None:
    """Render one year's Solar Pulse using the same radial-bar layout."""
    total_days = 366 if calendar.isleap(year) else 365

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

    for index, (date, actual, clear) in enumerate(rows):
        angle = 2 * math.pi * index / total_days
        radius = MAX_BAR_LENGTH * actual / scale_max

        # Actual / clear-sky controls visibility only.
        if clear > 0:
            transparency = max(0.30, min(actual / clear, 1.0))
        else:
            transparency = 0.55

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

    # Inner solar core.
    theta = np.linspace(0, 2 * math.pi, 360)
    ax.fill(
        theta,
        np.full_like(theta, INNER_RADIUS),
        color=BACKGROUND,
        zorder=10,
    )

    ax.text(
        0,
        0,
        f"{year}",
        color=TEXT,
        fontsize=18,
        ha="center",
        va="center",
        zorder=11,
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

    # Side information.
    fig.text(
        0.745,
        0.72,
        "VISUAL LOGIC\n\n"
        "One day = one radial bar\n"
        "Bar length = daily solar radiation\n"
        "Colour = radiation intensity\n"
        "Opacity = actual / clear-sky\n\n"
        "The same visual scale is used for\n"
        "all 26 years, so the animation\n"
        "remains comparable frame to frame.",
        color=TEXT,
        fontsize=9,
        va="top",
        linespacing=1.35,
    )

    fig.text(
        0.745,
        0.46,
        "DATA SOURCE\n\n"
        "NASA POWER\n"
        "ALLSKY_SFC_SW_DWN\n"
        "CLRSKY_SFC_SW_DWN\n"
        "Daily · Hong Kong\n"
        "2000–2025",
        color=TEXT,
        fontsize=9,
        va="top",
        linespacing=1.35,
    )

    fig.text(
        0.745,
        0.28,
        "THIS YEAR\n\n"
        f"Daily mean: {mean_value:.2f} kWh/m²/day\n"
        f"Peak: {max(values):.2f} kWh/m²/day",
        color=TEXT,
        fontsize=9,
        va="top",
        linespacing=1.35,
    )

    # Colour legend.
    fig.text(
        0.745,
        0.155,
        "DAILY SOLAR RADIATION\n"
        "(kWh/m²/day)",
        color=TEXT,
        fontsize=9,
        va="top",
        linespacing=1.3,
    )

    legend_ax = fig.add_axes([0.745, 0.105, 0.20, 0.022])
    gradient = np.linspace(0, scale_max, 256)[None, :]
    legend_ax.imshow(
        gradient,
        aspect="auto",
        cmap=SUN_CMAP,
        extent=[0, scale_max, 0, 1],
    )
    legend_ax.set_yticks([])
    legend_ax.set_xticks(np.linspace(0, scale_max, 5))
    legend_ax.set_xticklabels(
        [f"{x:.1f}" for x in np.linspace(0, scale_max, 5)],
        color=TEXT,
        fontsize=7,
    )
    for spine in legend_ax.spines.values():
        spine.set_visible(False)

    # A simple final sentence.
    fig.text(
        0.745,
        0.055,
        "The ring turns one year of sunlight into one pulse.",
        color=MUTED,
        fontsize=8.5,
        va="top",
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
