# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///

from pathlib import Path
import requests

HERE = Path(__file__).parent
DATA = HERE / "data" / "solar_pulse_2000_2025_raw.json"

URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
    "?parameters=ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN"
    "&community=RE"
    "&longitude=114.1694"
    "&latitude=22.3193"
    "&start=20000101"
    "&end=20251231"
    "&format=JSON"
)


def fetch_once(url: str, path: Path) -> None:
    """Download the NASA POWER reply once and save it unchanged."""
    if path.exists():
        print(f"Already exists: {path}")
        print("No download was made.")
        return

    response = requests.get(url, timeout=180)
    response.raise_for_status()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    print(f"Saved: {path}")
    print(f"Bytes: {len(response.content):,}")


if __name__ == "__main__":
    fetch_once(URL, DATA)
