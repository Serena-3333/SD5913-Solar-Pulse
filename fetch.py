# /// script
# requires-python = ">=3.10"
# dependencies = ["requests"]
# ///

from pathlib import Path
import requests

HERE = Path(__file__).parent
DATA = HERE / "data"
RAW_FILE = DATA / "solar_pulse_2025.json"

URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
    """?parameters=ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN&community=RE"""
    "&longitude=114.1694&latitude=22.3193"
    "&start=20250101&end=20251231&format=JSON"
)


def fetch_once() -> None:
    DATA.mkdir(exist_ok=True)

    if RAW_FILE.exists():
        print(f"Already have {RAW_FILE.name}; nothing to fetch.")
        return

    response = requests.get(URL, timeout=30)
    response.raise_for_status()
    RAW_FILE.write_bytes(response.content)
    print(f"Saved raw NASA POWER reply to {RAW_FILE}")


if __name__ == "__main__":
    fetch_once()
