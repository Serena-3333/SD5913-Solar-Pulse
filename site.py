# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///

"""Write the Solar Pulse page into site/: a full-viewport animation with one credit line."""

import shutil
from pathlib import Path

from PIL import Image, ImageSequence

HERE = Path(__file__).parent
SITE_DIR = HERE / "site"
OUT_DIR = HERE / "out"

GIF_NAME = "solar_pulse_2000_2025.gif"
WEBP_NAME = "solar_pulse_2000_2025.webp"
WEB_WIDTH = 1200
REPO_URL = "https://github.com/Serena-3333/SD5913-Solar-Pulse"
SOURCE_URL = "https://power.larc.nasa.gov/"

CSS = """
  html, body { width: 100%; height: 100%; margin: 0; padding: 0; }
  body { background: #07151C; }
  img { position: absolute; top: 0; bottom: 0; left: 0; right: 0;
        margin: auto; max-width: 100%; max-height: 100%; }
  footer { position: absolute; left: 0; right: 0; bottom: 0;
           color: #AEB5BA; font-size: 12px; padding: 12px 16px;
           font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; }
  footer a { color: #FFD42A; text-decoration: none; }
  footer a:hover { text-decoration: underline; }
"""


def build_webp() -> None:
    """Squeeze the committed GIF into a lighter animated WebP in out/."""
    frames = []
    durations = []
    with Image.open(OUT_DIR / GIF_NAME) as gif:
        for frame in ImageSequence.Iterator(gif):
            height = round(frame.height * WEB_WIDTH / frame.width)
            frames.append(frame.convert("RGB").resize((WEB_WIDTH, height), Image.LANCZOS))
            durations.append(frame.info.get("duration", 100))

    frames[0].save(
        OUT_DIR / WEBP_NAME,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        quality=75,
        method=6,
    )


def main() -> None:
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    build_webp()
    shutil.copy(OUT_DIR / WEBP_NAME, SITE_DIR / WEBP_NAME)

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Solar Pulse — Hong Kong</title>
<style>{CSS}</style>
</head>
<body>
  <img src="{WEBP_NAME}"
       alt="Daily solar radiation in Hong Kong: a polar chart of daily bars, morphing year by year from 2000 to 2025">
  <footer>Solar Pulse — Hong Kong ·
    <a href="{REPO_URL}">the repository</a> ·
    data from <a href="{SOURCE_URL}">NASA POWER</a></footer>
</body>
</html>
"""
    (SITE_DIR / "index.html").write_text(html, encoding="utf-8")
    size_mb = (SITE_DIR / WEBP_NAME).stat().st_size / 1e6
    print(f"Wrote {SITE_DIR / 'index.html'} and copied {WEBP_NAME} ({size_mb:.1f} MB) next to it")


if __name__ == "__main__":
    main()
