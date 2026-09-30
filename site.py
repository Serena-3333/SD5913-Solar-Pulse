# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///

"""Build the web page into site/ — the Solar Pulse animation, live.

Reads the committed NASA POWER data, computes the numbers the page shows
from it, writes a web-sized copy of the animation, and assembles
site/index.html around them. `uv run site.py` builds the page; the Pages
workflow runs the same line on GitHub's machine after every push.
site/ is output: it is never committed.
"""

import json
import shutil
from datetime import date
from pathlib import Path

from PIL import Image

HERE = Path(__file__).parent
DATA = HERE / "data" / "solar_pulse_2000_2025_raw.json"
OUT_DIR = HERE / "out"
SITE_DIR = HERE / "site"

STILL_NAME = "solar-pulse.png"
GIF_NAME = "solar_pulse_2000_2025.gif"
WEB_GIF_NAME = "solar_pulse_2000_2025_web.gif"
PAGE_GIF_WIDTH = 800

# The chart's palette, so the page's own picture speaks the same colours.
SUN_COLOURS = [
    "#25106A",
    "#5C1AA8",
    "#B51F7D",
    "#EC4E55",
    "#FF8B20",
    "#FFD42A",
    "#FFF3A5",
]
BACKGROUND = "#07151C"
CARD = "#0C1F2A"
EDGE = "#17313F"
TEXT = "#F2F1EC"
MUTED = "#AEB5BA"
ACCENT = "#FFD42A"

REPO_URL = "https://github.com/Serena-3333/SD5913-assignment2-Solar-Pulse"
SOURCE_URL = "https://power.larc.nasa.gov/"


def daily_radiation(payload):
    """(date, all-sky value) for every day, in calendar order.

    NASA fills missing readings with -999; the chart treats those days
    as zero, so the page does the same.
    """
    series = payload["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]
    days = []
    for key in sorted(series):
        if not key[:8].isdigit():
            continue
        value = max(float(series[key]), 0.0)
        days.append((date(int(key[:4]), int(key[4:6]), int(key[6:8])), value))
    return days


def annual_means(days):
    """The mean all-sky radiation of each year — the page's numbers come
    from this loop over the committed file, not from a hardcoded table."""
    by_year = {}
    for day, value in days:
        by_year.setdefault(day.year, []).append(value)
    return {year: sum(values) / len(values) for year, values in sorted(by_year.items())}


def colour_for(fraction):
    """Lerp along the chart's seven sun colours — matplotlib stays out of
    the site build, so the page needs only Pillow."""
    stops = [tuple(int(stop[i:i + 2], 16) for i in (1, 3, 5)) for stop in SUN_COLOURS]
    span = max(0.0, min(fraction, 1.0)) * (len(stops) - 1)
    index = min(int(span), len(stops) - 2)
    low, high = stops[index], stops[index + 1]
    step = span - index
    mixed = (round(low[c] + (high[c] - low[c]) * step) for c in range(3))
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def web_sized_gif(destination: Path):
    """Rewrite the animation at page width, keeping every frame's timing.

    Each frame is resampled in RGB, then remapped onto the animation's
    own 256-colour palette, so the smaller file shows the same colours
    as the original rather than a re-guessed palette per frame.
    """
    source = Image.open(OUT_DIR / GIF_NAME)
    source.seek(0)
    palette_holder = source.copy()
    width = PAGE_GIF_WIDTH
    height = round(source.height * width / source.width)

    frames, durations = [], []
    for index in range(source.n_frames):
        source.seek(index)
        durations.append(source.info.get("duration", 45))
        frame = source.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        frames.append(frame.quantize(palette=palette_holder, dither=Image.Dither.NONE))

    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
    )
    return width, height, len(frames)


def year_strip_svg(means):
    """One thin bar per year — a small picture the page makes for itself
    out of the annual means, on the chart's own colour scale."""
    values = list(means.values())
    low, high = min(values), max(values)
    span = high - low
    bars = []
    for position, (year, mean) in enumerate(means.items()):
        fraction = (mean - low) / span if span > 0 else 0.5
        bar_height = 6 + 44 * fraction
        x = position * 14
        bars.append(
            f'<rect x="{x}" y="{54 - bar_height:.1f}" width="10" '
            f'height="{bar_height:.1f}" rx="2" fill="{colour_for(fraction)}"/>'
        )
        bars.append(
            f'<text x="{x + 5}" y="63" fill="{MUTED}" font-size="7" '
            f'text-anchor="middle">{year % 100:02d}</text>'
        )
    return (
        f'<svg viewBox="0 0 {len(means) * 14} 66" width="100%" '
        f'role="img" aria-label="Mean daily solar radiation per year">'
        f'{"".join(bars)}</svg>'
    )


CSS = """
  body { background: #07151C; color: #F2F1EC; margin: 0;
         font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; }
  main { max-width: 900px; margin: 0 auto; padding: 44px 20px 60px; }
  h1 { font-size: 34px; margin: 0 0 6px; letter-spacing: 0.5px; }
  .sub { color: #AEB5BA; font-size: 15px; margin: 0 0 30px; }
  img { width: 100%; border-radius: 12px; display: block; }
  figure { margin: 0; }
  figcaption { color: #AEB5BA; font-size: 13px; padding: 9px 2px 36px; }
  h2 { font-size: 20px; margin: 36px 0 12px; }
  p { font-size: 15px; line-height: 1.65; }
  .facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
           gap: 14px; }
  .fact { background: #0C1F2A; border: 1px solid #17313F; border-radius: 10px;
          padding: 14px 16px; }
  .fact span { color: #AEB5BA; font-size: 12px; text-transform: uppercase;
               letter-spacing: 0.6px; }
  .fact b { display: block; font-size: 22px; color: #FFD42A; margin-top: 5px;
            font-weight: 600; }
  .fact small { display: block; color: #AEB5BA; font-size: 11px; margin-top: 2px; }
  .years { margin-top: 14px; }
  code { background: #0C1F2A; border: 1px solid #17313F; border-radius: 6px;
         padding: 2px 7px; font-size: 13px; }
  footer { color: #AEB5BA; font-size: 13px; border-top: 1px solid #17313F;
           margin-top: 44px; padding-top: 18px; line-height: 1.8; }
  a { color: #FFD42A; text-decoration: none; }
  a:hover { text-decoration: underline; }
"""


def main() -> None:
    days = daily_radiation(json.loads(DATA.read_text(encoding="utf-8")))
    means = annual_means(days)
    values = [value for _, value in days]
    overall_mean = sum(values) / len(values)
    peak = max(values)
    sunniest = max(means, key=means.get)
    dullest = min(means, key=means.get)
    first_year, last_year = min(means), max(means)

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(OUT_DIR / STILL_NAME, SITE_DIR / STILL_NAME)
    width, height, frame_count = web_sized_gif(SITE_DIR / WEB_GIF_NAME)

    fact = lambda label, value, note: (
        f'<div class="fact"><span>{label}</span><b>{value}</b><small>{note}</small></div>'
    )
    facts = "".join([
        fact("Years", f"{first_year}–{last_year}", "one bar per day, in order"),
        fact("Days", f"{len(days):,}", "committed readings in data/"),
        fact("Average day", f"{overall_mean:.2f}", "kWh/m²/day, all-sky"),
        fact("Peak day", f"{peak:.2f}", "kWh/m²/day, all-sky"),
        fact("Sunniest year", f"{sunniest}", f"mean {means[sunniest]:.2f} kWh/m²/day"),
        fact("Dullest year", f"{dullest}", f"mean {means[dullest]:.2f} kWh/m²/day"),
    ])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Pulse — Hong Kong</title>
<style>{CSS}</style>
</head>
<body>
<main>
  <h1>Solar Pulse — Hong Kong</h1>
  <p class="sub">Daily solar radiation, morphing year by year from {first_year} to {last_year} · NASA POWER</p>

  <figure>
    <img src="{WEB_GIF_NAME}" alt="Animated polar chart: one bar per day of the year,
      morphing from {first_year} to {last_year} as the centre year counts up">
    <figcaption>The animation — {frame_count} frames, {width}&times;{height} on the page.
    The <a href="{REPO_URL}/blob/main/out/{GIF_NAME}">full-resolution original</a> sits in
    the repository's <code>out/</code>.</figcaption>
  </figure>

  <figure>
    <img src="{STILL_NAME}" alt="Still polar chart of daily solar radiation in Hong Kong during 2025">
    <figcaption>The 2025 chart as a still — the same shape the animation rests on at each year.</figcaption>
  </figure>

  <h2>The numbers behind it</h2>
  <div class="facts">{facts}</div>
  <div class="years">{year_strip_svg(means)}</div>
  <p><small style="color:{MUTED}">Each bar above is one year's mean daily all-sky
  radiation, drawn on the chart's own colour scale.</small></p>

  <h2>Where the numbers come from</h2>
  <p>The <a href="{SOURCE_URL}">NASA POWER</a> daily point API for Hong Kong
  (22.3193&nbsp;N, 114.1694&nbsp;E). The file holds one row per day — the all-sky
  and clear-sky surface shortwave radiation in kWh/m²/day — fetched once and
  committed unchanged to <code>data/</code>. The site is rebuilt from that
  committed file on every push, with the wifi off if need be.</p>

  <h2>How it is made</h2>
  <p><code>uv run fetch.py</code> fetches once · <code>uv run plot.py</code> draws the
  still · <code>uv run animate.py</code> morphs the years into a GIF ·
  <code>uv run site.py</code> builds this page.</p>

  <footer>
    <a href="{REPO_URL}">The repository</a> ·
    data from <a href="{SOURCE_URL}">NASA POWER</a> ·
    built from the committed data, rebuilt on every push.
  </footer>
</main>
</body>
</html>
"""
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")

    web_bytes = (SITE_DIR / WEB_GIF_NAME).stat().st_size
    print(f"Wrote {SITE_DIR / 'index.html'}")
    print(f"Page animation: {WEB_GIF_NAME} — {width}x{height}, "
          f"{frame_count} frames, {web_bytes / 1e6:.1f} MB "
          f"(original GIF is {(OUT_DIR / GIF_NAME).stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
