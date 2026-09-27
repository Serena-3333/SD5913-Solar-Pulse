# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib"]
# ///

from pathlib import Path
import json
import math

import matplotlib.pyplot as plt

HERE = Path(__file__).parent
DATA_FILE = HERE / "data" / "solar_pulse_2025.json"
OUT_FILE = HERE / "out" / "solar-pulse.png"


def load_solar_data(path: Path) -> list[tuple[str, float, float]]:
    """Return (date, actual_radiation, clear_sky_radiation) for every day."""
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    parameters = data["properties"]["parameter"]
    actual = parameters["ALLSKY_SFC_SW_DWN"]
    clear = parameters["CLRSKY_SFC_SW_DWN"]

    rows = []
    for date in sorted(actual):
        rows.append((date, float(actual[date]), float(clear[date])))
    return rows


def sky_factor(actual: float, clear: float) -> float:
    """Compare actual solar radiation with the clear-sky value."""
    if clear <= 0:
        return 0.0
    return max(0.0, min(actual / clear, 1.0))


def draw_solar_pulse(rows: list[tuple[str, float, float]]) -> None:
    values = [row[1] for row in rows]
    max_value = max(values)

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw={"projection": "polar"})
    ax.set_theta_direction(-1)
    ax.set_theta_offset(math.pi / 2)

    width = 2 * math.pi / len(rows) * 0.92

    for index, (date, actual, clear) in enumerate(rows):
        angle = 2 * math.pi * index / len(rows)
        radius = actual / max_value * 4.0
        transparency = sky_factor(actual, clear)

        ax.bar(
            angle,
            radius,
            width=width,
            bottom=1.0,
            alpha=0.25 + 0.75 * transparency,
            linewidth=0,
        )

    ax.set_title("Solar Pulse — Hong Kong, 2025", pad=28, fontsize=18)
    ax.set_yticklabels([])
    ax.set_xticks([2 * math.pi * i / 12 for i in range(12)])
    ax.set_xticklabels(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    )
    ax.grid(alpha=0.15)

    fig.text(
        0.5,
        0.03,
        "Length = daily all-sky solar radiation · opacity = actual / clear-sky radiation",
        ha="center",
        fontsize=10,
    )

    OUT_FILE.parent.mkdir(exist_ok=True)
    fig.savefig(OUT_FILE, dpi=200, bbox_inches="tight")
    plt.show()
    print(f"Saved {OUT_FILE}")


if __name__ == "__main__":
    rows = load_solar_data(DATA_FILE)
    print(f"Loaded {len(rows)} daily records")
    draw_solar_pulse(rows)
