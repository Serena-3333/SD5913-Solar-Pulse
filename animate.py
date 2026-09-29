# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib", "pillow"]
# ///

from pathlib import Path

from PIL import Image

from plot import (
    DATA,
    END_YEAR,
    OUT_DIR,
    RADIATION_MAX,
    START_YEAR,
    group_by_year,
    load_raw,
    render_year,
)

FRAMES_DIR = OUT_DIR / 'frames'

def global_scale(years):
    return RADIATION_MAX



def main() -> None:
    payload = load_raw(DATA)
    years = group_by_year(payload)

    expected = list(range(START_YEAR, END_YEAR + 1))
    missing = [year for year in expected if year not in years]
    if missing:
        raise ValueError(f"Missing years in raw data: {missing}")

    scale_max = global_scale(years)

    frames = []

    for year in expected:
        path = FRAMES_DIR / f"solar_pulse_{year}.png"
        render_year(year, years[year], scale_max, path)

        with Image.open(path) as image:
            frames.append(image.convert("RGB"))

        print(f"Rendered {year}")

    # Quantize every frame with one shared palette so GIF colours do not
    # change from frame to frame.
    palette_sample_size = 1024
    palette_samples = Image.new(
        "RGB",
        (palette_sample_size, palette_sample_size * len(frames)),
    )
    for index, frame in enumerate(frames):
        sample = frame.copy()
        sample.thumbnail((palette_sample_size, palette_sample_size))
        palette_samples.paste(sample, (0, index * palette_sample_size))

    palette = palette_samples.quantize(colors=256)
    indexed_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.NONE)
        for frame in frames
    ]
    palette_samples.close()

    gif_path = Path(__file__).parent / "out" / "solar_pulse_2000_2025.gif"

    indexed_frames[0].save(
        gif_path,
        save_all=True,
        append_images=indexed_frames[1:],
        duration=200,
        loop=0,
        optimize=False,
    )

    for image in frames:
        image.close()
    for image in indexed_frames:
        image.close()

    print(f"Saved: {gif_path}")


if __name__ == "__main__":
    main()
