# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "pillow"]
# ///

import os

os.environ.setdefault("MPLBACKEND", "Agg")

import math
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import PolyCollection
from matplotlib.figure import Figure
from PIL import Image

from plot import (
    BACKGROUND,
    DATA,
    INNER_RADIUS,
    MAX_BAR_LENGTH,
    MUTED,
    OUT_DIR,
    RADIATION_MAX,
    SUN_CMAP,
    TEXT,
    draw_solar_core,
    draw_time_scaffold,
    group_by_year,
    load_raw,
    month_labels,
)

FRAMES_DIR = OUT_DIR / "frames"
GIF_PATH = OUT_DIR / "solar_pulse_2000_2025.gif"
ANIMATION_START_YEAR = 2000
ANIMATION_END_YEAR = 2025
FRAMES_PER_YEAR = 12
ANNUAL_DURATION_MS = 300
TRANSITION_DURATION_MS = 45
FIXED_DAY_COUNT = 365
RENDER_DPI = 120

DAY_ANGLES = 2.0 * math.pi * np.arange(FIXED_DAY_COUNT) / FIXED_DAY_COUNT
HALF_BAR_WIDTH = math.pi / FIXED_DAY_COUNT * 0.92


def smoothstep(value: float) -> float:
    """Ease interpolation without adding a secondary motion effect."""
    return value * value * (3.0 - 2.0 * value)


def fixed_day_index(date) -> int:
    """Map month/day to one non-leap-year position.

    February 29 is folded into February 28. March 1 therefore keeps the same
    position in every year, so leap years never shift all later dates.
    """
    if date.month == 2 and date.day == 29:
        return 58
    reference_date = date.replace(year=2001)
    return reference_date.timetuple().tm_yday - 1


def fixed_day_rows(rows):
    """Return 365 values, averaging February 29 into February 28."""
    values = [[] for _ in range(FIXED_DAY_COUNT)]
    for date, actual, clear in rows:
        values[fixed_day_index(date)].append((actual, clear))

    normalized = []
    for day_values in values:
        if not day_values:
            normalized.append((0.0, 0.0))
            continue
        normalized.append(
            (
                sum(actual for actual, _ in day_values) / len(day_values),
                sum(clear for _, clear in day_values) / len(day_values),
            )
        )
    return normalized


def year_arrays(rows) -> dict:
    """Precompute the per-year 365-day vectors shared by every frame."""
    fixed = fixed_day_rows(rows)
    actual = np.array([value for value, _ in fixed])
    clear = np.array([value for _, value in fixed])

    # Actual / clear-sky ratio drives visibility only (capped at 0.30).
    ratio = actual / np.where(clear > 0, clear, 1.0)
    alpha = np.where(clear > 0, np.clip(ratio, 0.30, 1.0), 0.55)

    return {
        "actual": actual,
        "rgba": SUN_CMAP(np.clip(actual / RADIATION_MAX, 0.0, 1.0)),
        "alpha": alpha,
        "mean": float(actual.sum() / FIXED_DAY_COUNT),
        "peak": float(actual.max()),
    }


def wedge_verts(angles, bottom: float, heights, half_widths):
    """Build (N, 4, 2) wedge polygons — the same four corners a polar
    Rectangle spans, so the rendered geometry matches bar() exactly."""
    left = angles - half_widths
    right = angles + half_widths
    top = bottom + heights
    verts = np.empty((angles.size, 4, 2))
    verts[:, 0, 0], verts[:, 0, 1] = left, bottom
    verts[:, 1, 0], verts[:, 1, 1] = right, bottom
    verts[:, 2, 0], verts[:, 2, 1] = right, top
    verts[:, 3, 0], verts[:, 3, 1] = left, top
    return verts


def render_morph_frame(
    start_year: int,
    end_year: int,
    start: dict,
    end: dict,
    progress: float,
    palette=None,
) -> Image.Image:
    """Render a morph frame with a synchronized whole-chart heartbeat pulse.

    Returns an RGB image, or a palette-quantized one when a shared GIF palette
    is supplied. The bars are drawn as three vectorized wedge collections
    (outer glow, rays, inner glow) instead of one ax.bar() call per day.
    """
    actual = start["actual"] + (end["actual"] - start["actual"]) * progress
    rgba = start["rgba"] + (end["rgba"] - start["rgba"]) * progress
    alpha = start["alpha"] + (end["alpha"] - start["alpha"]) * progress
    radius = MAX_BAR_LENGTH * actual / RADIATION_MAX

    pulse = math.sin(math.pi * progress)
    chart_scale = 1.0 + 0.045 * pulse
    base_left, base_bottom, base_width, base_height = 0.045, 0.075, 0.67, 0.82
    ax_position = [
        base_left - base_width * (chart_scale - 1.0) / 2,
        base_bottom - base_height * (chart_scale - 1.0) / 2,
        base_width * chart_scale,
        base_height * chart_scale,
    ]

    fig = Figure(figsize=(12, 10), dpi=RENDER_DPI, facecolor=BACKGROUND)
    FigureCanvasAgg(fig)
    ax = fig.add_axes(ax_position, projection="polar", facecolor=BACKGROUND)
    ax.set_theta_direction(-1)
    ax.set_theta_offset(math.pi / 2)

    draw_time_scaffold(ax, FIXED_DAY_COUNT)

    intensity = np.clip(actual / RADIATION_MAX, 0.0, 1.0)
    bloom = intensity > 0.60
    if bloom.any():
        # Glow follows the interpolated intensity; the ray remains the data mark.
        bloom_strength = (intensity[bloom] - 0.60) / 0.40
        angles = DAY_ANGLES[bloom]
        glow = rgba[bloom]
        outer_colors = glow.copy()
        outer_colors[:, 3] = 0.018 + bloom_strength * 0.035
        inner_colors = glow.copy()
        inner_colors[:, 3] = 0.025 + bloom_strength * 0.075
        outer_verts = wedge_verts(angles, INNER_RADIUS, radius[bloom] + 0.18, HALF_BAR_WIDTH * 2.35)
        inner_verts = wedge_verts(angles, INNER_RADIUS, radius[bloom] + 0.08, HALF_BAR_WIDTH * 1.55)

        outer = PolyCollection(outer_verts, facecolors=outer_colors, linewidths=0,
                               zorder=1, closed=True)
        ax.add_collection(outer)
        ax.update_datalim(outer_verts.reshape(-1, 2))

    # One fixed ray is retained: radius is interpolated, never removed and
    # recreated at a new angle between two years.
    main_colors = rgba.copy()
    main_colors[:, 3] = alpha
    main_verts = wedge_verts(DAY_ANGLES, INNER_RADIUS, radius, HALF_BAR_WIDTH)
    main = PolyCollection(main_verts, facecolors=main_colors, linewidths=0,
                          zorder=1, closed=True)
    ax.add_collection(main)
    ax.update_datalim(main_verts.reshape(-1, 2))

    if bloom.any():
        inner = PolyCollection(inner_verts, facecolors=inner_colors, linewidths=0,
                               zorder=2, closed=True)
        ax.add_collection(inner)
        ax.update_datalim(inner_verts.reshape(-1, 2))

    ax.set_ylim(0, INNER_RADIUS + MAX_BAR_LENGTH + 0.45)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    ax.spines["polar"].set_visible(False)

    draw_solar_core(ax, pulse)

    # The center year crossfades while the bars themselves morph continuously.
    ax.text(0, 0, f"{start_year}", color=TEXT, alpha=1.0 - progress,
            fontsize=18, ha="center", va="center", zorder=12)
    ax.text(0, 0, f"{end_year}", color=TEXT, alpha=progress,
            fontsize=18, ha="center", va="center", zorder=12)

    for theta_value, label in month_labels(2001):
        ax.text(
            theta_value,
            INNER_RADIUS + MAX_BAR_LENGTH + 0.28,
            label,
            color=TEXT,
            fontsize=10,
            ha="center",
            va="center",
        )

    fig.text(0.045, 0.955, "Solar Pulse — Hong Kong", color=TEXT,
             fontsize=25, ha="left", va="top")
    display_year = start_year if progress < 0.5 else end_year
    fig.text(0.045, 0.915, f"{display_year}  ·  annual frame",
             color="#FFFFFF", fontsize=10, ha="left", va="top")

    mean_value = start["mean"] + (end["mean"] - start["mean"]) * progress
    peak_value = start["peak"] + (end["peak"] - start["peak"]) * progress

    fig.text(0.745, 0.76, "SOLAR RADIATION", color=TEXT,
             fontsize=11, va="top")
    legend_ax = fig.add_axes([0.745, 0.685, 0.20, 0.022])
    gradient = np.linspace(0, RADIATION_MAX, 256)[None, :]
    legend_ax.imshow(gradient, aspect="auto", cmap=SUN_CMAP,
                     extent=[0, RADIATION_MAX, 0, 1])
    legend_ax.set_yticks([])
    tick_values = np.linspace(0, RADIATION_MAX, 5)
    legend_ax.set_xticks(tick_values)
    legend_ax.set_xticklabels([f"{value:.1f}" for value in tick_values],
                              color=TEXT, fontsize=7)
    legend_ax.tick_params(axis="x", colors=TEXT, length=2, pad=2)
    for spine in legend_ax.spines.values():
        spine.set_visible(False)
    fig.text(0.745, 0.55, "NASA POWER\nHong Kong · 2000–2025",
             color=MUTED, fontsize=9, va="top", linespacing=1.5)
    fig.text(0.745, 0.39, f"{start_year}", color=TEXT,
             alpha=1.0 - progress, fontsize=24, va="top")
    fig.text(0.745, 0.39, f"{end_year}", color=TEXT,
             alpha=progress, fontsize=24, va="top")
    fig.text(0.745, 0.32,
             f"Mean  {mean_value:.2f} kWh/m²/day\n"
             f"Peak   {peak_value:.2f} kWh/m²/day",
             color=MUTED, fontsize=8.5, va="top", linespacing=1.7)

    fig.canvas.draw()
    width, height = fig.canvas.get_width_height()
    image = Image.frombuffer(
        "RGBA", (width, height), fig.canvas.buffer_rgba(), "raw", "RGBA", 0, 1
    ).convert("RGB")
    if palette is not None:
        image = image.quantize(palette=palette, dither=Image.Dither.NONE)
    return image


def build_frame_specs(years: dict):
    """One starting frame, then each morph and its yearly endpoint."""
    ordered = sorted(years)
    specs = [("still", ordered[0], ordered[0], 1.0, None)]
    for start_year, end_year in zip(ordered, ordered[1:]):
        for number in range(1, FRAMES_PER_YEAR + 1):
            progress = smoothstep(number / (FRAMES_PER_YEAR + 1))
            specs.append(("morph", start_year, end_year, progress, number))
        specs.append(("still", end_year, end_year, 1.0, None))

    durations = [
        ANNUAL_DURATION_MS if spec[0] == "still" else TRANSITION_DURATION_MS
        for spec in specs
    ]
    return specs, durations


def frame_path(spec, frames_dir: Path) -> Path:
    kind, start_year, end_year, _progress, number = spec
    if kind == "still":
        return frames_dir / f"solar_pulse_{start_year}.png"
    return frames_dir / f"morph_{start_year}_{end_year}_{number:02d}.png"


_STATE = {}


def _worker_init(year_data, palette, frames_dir):
    _STATE["years"] = year_data
    _STATE["palette"] = palette
    _STATE["frames_dir"] = frames_dir


def _render_spec(spec):
    kind, start_year, end_year, progress, _number = spec
    image = render_morph_frame(
        start_year,
        end_year,
        _STATE["years"][start_year],
        _STATE["years"][end_year],
        progress,
        palette=_STATE["palette"],
    )
    image.save(frame_path(spec, _STATE["frames_dir"]))
    image.close()


def main() -> None:
    started = time.perf_counter()
    payload = load_raw(DATA)
    all_years = group_by_year(payload)
    available_years = {
        year: all_years[year]
        for year in range(ANIMATION_START_YEAR, ANIMATION_END_YEAR + 1)
        if year in all_years
    }
    missing_years = [
        year for year in range(ANIMATION_START_YEAR, ANIMATION_END_YEAR + 1)
        if year not in available_years
    ]
    if missing_years:
        print(f"Data unavailable for {missing_years}; using available years only.")
    if len(available_years) < 2:
        raise ValueError("At least two adjacent years are required for morphing.")

    year_data = {year: year_arrays(rows) for year, rows in available_years.items()}
    specs, durations = build_frame_specs(available_years)

    # Build the shared GIF palette from a few small representative frames.
    sample_indices = sorted(set(
        [0, len(specs) // 4, len(specs) // 2, (3 * len(specs)) // 4, len(specs) - 1]
    ))
    samples = []
    for index in sample_indices:
        _kind, start_year, end_year, progress, _number = specs[index]
        frame = render_morph_frame(
            start_year, end_year,
            year_data[start_year], year_data[end_year],
            progress,
        )
        sample = frame.copy()
        sample.thumbnail((256, 256))
        samples.append(sample)
        frame.close()

    palette_canvas = Image.new("RGB", (256, 256 * len(samples)))
    for index, sample in enumerate(samples):
        palette_canvas.paste(sample, (0, index * 256))
    palette = palette_canvas.quantize(colors=256)

    for sample in samples:
        sample.close()
    palette_canvas.close()

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    render_started = time.perf_counter()
    workers = os.cpu_count() or 1
    if workers > 1:
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_init,
            initargs=(year_data, palette, FRAMES_DIR),
        ) as pool:
            list(pool.map(_render_spec, specs, chunksize=4))
    else:
        _worker_init(year_data, palette, FRAMES_DIR)
        for spec in specs:
            _render_spec(spec)
    print(f"Rendered {len(specs)} frames on {workers} workers in "
          f"{time.perf_counter() - render_started:.1f}s")

    # Stream the quantized frames from disk while assembling the GIF.
    def frames_from_disk():
        for spec in specs:
            image = Image.open(frame_path(spec, FRAMES_DIR))
            image.load()
            yield image

    gif_started = time.perf_counter()
    frame_iter = frames_from_disk()
    first = next(frame_iter)
    first.save(
        GIF_PATH,
        save_all=True,
        append_images=frame_iter,
        duration=durations,
        loop=0,
        optimize=False,
    )
    frame_iter.close()
    first.close()
    print(f"Assembled GIF in {time.perf_counter() - gif_started:.1f}s")

    print(f"Saved: {GIF_PATH}")
    print(f"Total: {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
