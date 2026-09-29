# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "pillow"]
# ///

from pathlib import Path
import calendar
import math

import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import numpy as np
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
    colour_for,
    draw_solar_core,
    draw_time_scaffold,
    group_by_year,
    load_raw,
    month_labels,
)

FRAMES_DIR = OUT_DIR / "frames"
ANIMATION_START_YEAR = 2000
ANIMATION_END_YEAR = 2025
FRAMES_PER_YEAR = 12
ANNUAL_DURATION_MS = 300
TRANSITION_DURATION_MS = 45
FIXED_DAY_COUNT = 365
RENDER_DPI = 120


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


def interpolate_values(start, end, progress: float):
    """Interpolate matching daily values while keeping their fixed angles."""
    return [
        start_value + (end_value - start_value) * progress
        for start_value, end_value in zip(start, end)
    ]


def visibility(actual: float, clear: float) -> float:
    if clear > 0:
        return max(0.30, min(actual / clear, 1.0))
    return 0.55


def load_frame(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def render_morph_frame(
    start_year: int,
    end_year: int,
    start_rows,
    end_rows,
    scale_max: float,
    progress: float,
    output_path: Path,
    prepared=None,
) -> None:
    """Render a morph frame with a synchronized whole-chart heartbeat pulse."""
    if prepared is None:
        start_values = fixed_day_rows(start_rows)
        end_values = fixed_day_rows(end_rows)
        start_actual = [actual for actual, _ in start_values]
        end_actual = [actual for actual, _ in end_values]
        start_clear = [clear for _, clear in start_values]
        end_clear = [clear for _, clear in end_values]
    else:
        start_actual, end_actual, start_clear, end_clear = prepared
    actual_values = interpolate_values(start_actual, end_actual, progress)
    clear_values = interpolate_values(start_clear, end_clear, progress)

    pulse = math.sin(math.pi * progress)
    chart_scale = 1.0 + 0.045 * pulse
    base_left, base_bottom, base_width, base_height = 0.045, 0.075, 0.67, 0.82
    ax_position = [
        base_left - base_width * (chart_scale - 1.0) / 2,
        base_bottom - base_height * (chart_scale - 1.0) / 2,
        base_width * chart_scale,
        base_height * chart_scale,
    ]

    fig = plt.figure(figsize=(12, 10), dpi=RENDER_DPI, facecolor=BACKGROUND)
    ax = fig.add_axes(
        ax_position,
        projection="polar",
        facecolor=BACKGROUND,
    )
    ax.set_theta_direction(-1)
    ax.set_theta_offset(math.pi / 2)
    width = 2 * math.pi / FIXED_DAY_COUNT * 0.92

    draw_time_scaffold(ax, FIXED_DAY_COUNT)

    for index, (actual, clear) in enumerate(zip(actual_values, clear_values)):
        angle = 2 * math.pi * index / FIXED_DAY_COUNT
        radius_start = MAX_BAR_LENGTH * start_actual[index] / scale_max
        radius_end = MAX_BAR_LENGTH * end_actual[index] / scale_max
        # radius(t) = radius_start + (radius_end - radius_start) * t
        radius = radius_start + (radius_end - radius_start) * progress

        # One fixed ray is retained: radius is interpolated, never removed and
        # recreated at a new angle between two years.
        start_colour = np.asarray(to_rgba(colour_for(start_actual[index], scale_max)))
        end_colour = np.asarray(to_rgba(colour_for(end_actual[index], scale_max)))
        colour = start_colour + (end_colour - start_colour) * progress
        start_alpha = visibility(start_actual[index], start_clear[index])
        end_alpha = visibility(end_actual[index], end_clear[index])
        alpha = start_alpha + (end_alpha - start_alpha) * progress

        # Glow follows the interpolated intensity; the ray remains the data mark.
        intensity = max(0.0, min(actual / scale_max, 1.0))
        if intensity > 0.60:
            bloom_strength = (intensity - 0.60) / 0.40
            ax.bar(
                angle,
                radius + 0.18,
                width=width * 2.35,
                bottom=INNER_RADIUS,
                color=colour,
                alpha=0.018 + bloom_strength * 0.035,
                linewidth=0,
                align="center",
                zorder=1,
            )
            ax.bar(
                angle,
                radius + 0.08,
                width=width * 1.55,
                bottom=INNER_RADIUS,
                color=colour,
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
            color=colour,
            alpha=alpha,
            linewidth=0,
            align="center",
        )

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

    start_mean = sum(start_actual) / FIXED_DAY_COUNT
    end_mean = sum(end_actual) / FIXED_DAY_COUNT
    start_peak = max(start_actual)
    end_peak = max(end_actual)
    mean_value = start_mean + (end_mean - start_mean) * progress
    peak_value = start_peak + (end_peak - start_peak) * progress

    fig.text(0.745, 0.76, "SOLAR RADIATION", color=TEXT,
             fontsize=11, va="top")
    legend_ax = fig.add_axes([0.745, 0.685, 0.20, 0.022])
    gradient = np.linspace(0, scale_max, 256)[None, :]
    legend_ax.imshow(gradient, aspect="auto", cmap=SUN_CMAP,
                     extent=[0, scale_max, 0, 1])
    legend_ax.set_yticks([])
    tick_values = np.linspace(0, scale_max, 5)
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=RENDER_DPI, facecolor=BACKGROUND)
    plt.close(fig)


def build_transition_frames(years, scale_max):
    """Create one starting frame, then each morph and its yearly endpoint."""
    ordered_years = sorted(years)
    frames = []
    durations = []

    first_year = ordered_years[0]
    first_path = FRAMES_DIR / f"solar_pulse_{first_year}.png"
    render_morph_frame(
        first_year,
        first_year,
        years[first_year],
        years[first_year],
        scale_max,
        1.0,
        first_path,
    )
    frames.append(load_frame(first_path))
    durations.append(ANNUAL_DURATION_MS)

    for start_year, end_year in zip(ordered_years, ordered_years[1:]):
        # Cache date alignment once per year-to-year transition.
        start_fixed = fixed_day_rows(years[start_year])
        end_fixed = fixed_day_rows(years[end_year])
        prepared = (
            [actual for actual, _ in start_fixed],
            [actual for actual, _ in end_fixed],
            [clear for _, clear in start_fixed],
            [clear for _, clear in end_fixed],
        )

        for frame_number in range(1, FRAMES_PER_YEAR + 1):
            progress = smoothstep(frame_number / (FRAMES_PER_YEAR + 1))
            frame_path = FRAMES_DIR / f"morph_{start_year}_{end_year}_{frame_number:02d}.png"
            render_morph_frame(
                start_year,
                end_year,
                years[start_year],
                years[end_year],
                scale_max,
                progress,
                frame_path,
                prepared=prepared,
            )
            frames.append(load_frame(frame_path))
            durations.append(TRANSITION_DURATION_MS)

        # Keep the exact endpoint beside its transition, rather than placing
        # every annual still at the beginning of the animation.
        endpoint_path = FRAMES_DIR / f"solar_pulse_{end_year}.png"
        render_morph_frame(
            end_year,
            end_year,
            years[end_year],
            years[end_year],
            scale_max,
            1.0,
            endpoint_path,
        )
        frames.append(load_frame(endpoint_path))
        durations.append(ANNUAL_DURATION_MS)

    return frames, durations


def main() -> None:
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

    # Every frame uses this one fixed radiation scale; no yearly renormalization.
    frames, durations = build_transition_frames(available_years, RADIATION_MAX)

    # Build the shared GIF palette from a few small representative frames.
    # This avoids creating one huge image containing every full-size frame.
    sample_indices = sorted(set(
        [0, len(frames) // 4, len(frames) // 2, (3 * len(frames)) // 4, len(frames) - 1]
    ))
    samples = []
    for index in sample_indices:
        sample = frames[index].copy()
        sample.thumbnail((256, 256))
        samples.append(sample)

    palette_samples = Image.new("RGB", (256, 256 * len(samples)))
    for index, sample in enumerate(samples):
        palette_samples.paste(sample, (0, index * 256))

    palette = palette_samples.quantize(colors=256)
    indexed_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE)
        for frame in frames
    ]

    for sample in samples:
        sample.close()
    palette_samples.close()

    gif_path = OUT_DIR / "solar_pulse_2000_2025.gif"
    indexed_frames[0].save(
        gif_path,
        save_all=True,
        append_images=indexed_frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )

    for image in frames + indexed_frames:
        image.close()

    print(f"Saved: {gif_path}")


if __name__ == "__main__":
    main()
