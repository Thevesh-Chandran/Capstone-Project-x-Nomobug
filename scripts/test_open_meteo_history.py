import csv
import json
import sys
from datetime import date
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch(latitude, longitude, start_date, end_date, timezone="Asia/Kuala_Lumpur"):
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start_date,
        "end_date": end_date,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,rain_sum",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation,rain",
        "timezone": timezone,
        "temperature_unit": "celsius",
        "precipitation_unit": "mm",
        "timeformat": "iso8601",
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    req = Request(url, headers={"User-Agent": "NomobugCapstone/1.0"})
    with urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    if len(sys.argv) < 4:
        print(
            "Usage: python test_open_meteo_history.py latitude longitude start_date end_date\n"
            "Example: python test_open_meteo_history.py 3.0738 101.5183 2026-06-01 2026-06-24"
        )
        raise SystemExit(1)

    latitude = float(sys.argv[1])
    longitude = float(sys.argv[2])
    start_date = sys.argv[3]
    end_date = sys.argv[4] if len(sys.argv) > 4 else date.today().isoformat()

    payload = fetch(latitude, longitude, start_date, end_date)

    out_path = "open_meteo_history_sample.csv"
    daily = payload.get("daily", {})
    hourly = payload.get("hourly", {})

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "time", "weather_code", "temperature_2m_max", "temperature_2m_min", "precipitation_sum", "rain_sum", "temperature_2m", "relative_humidity_2m", "hourly_precipitation", "hourly_rain"])

        for i, t in enumerate(daily.get("time", [])):
            writer.writerow([
                "daily",
                t,
                daily.get("weather_code", [None])[i] if i < len(daily.get("weather_code", [])) else None,
                daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
                daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
                daily.get("precipitation_sum", [None])[i] if i < len(daily.get("precipitation_sum", [])) else None,
                daily.get("rain_sum", [None])[i] if i < len(daily.get("rain_sum", [])) else None,
                None,
                None,
                None,
                None,
            ])

        for i, t in enumerate(hourly.get("time", [])):
            writer.writerow([
                "hourly",
                t,
                None,
                None,
                None,
                None,
                None,
                hourly.get("temperature_2m", [None])[i] if i < len(hourly.get("temperature_2m", [])) else None,
                hourly.get("relative_humidity_2m", [None])[i] if i < len(hourly.get("relative_humidity_2m", [])) else None,
                hourly.get("precipitation", [None])[i] if i < len(hourly.get("precipitation", [])) else None,
                hourly.get("rain", [None])[i] if i < len(hourly.get("rain", [])) else None,
            ])

    print(f"Saved sample weather data to {out_path}")
    print(f"Latitude: {payload.get('latitude')}, Longitude: {payload.get('longitude')}")
    print(f"Timezone: {payload.get('timezone')}")
    print(f"Daily rows: {len(daily.get('time', []))}, Hourly rows: {len(hourly.get('time', []))}")


if __name__ == "__main__":
    main()
