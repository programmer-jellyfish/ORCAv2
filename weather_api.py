"""
weather_api.py
Fetches live wind / rain / weather data from the Open-Meteo Weather API.
Falls back to labeled demo reference data if the API is unreachable
or returns an incomplete payload. Never fabricates live data silently.
"""

import os
import json
import requests

DEMO_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
REQUEST_TIMEOUT = 6


def _load_demo():
    with open(DEMO_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_weather_data(zone_key, lat, lon):
    """
    Returns a dict with wind_speed_kmh, wind_gusts_kmh,
    precipitation_probability, precipitation_mm, source, provider.
    """
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "wind_speed_10m,wind_gusts_10m,precipitation,weather_code",
            "hourly": "precipitation_probability",
            "wind_speed_unit": "kmh",
            "timezone": "auto",
            "forecast_days": 1,
        }
        resp = requests.get(WEATHER_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        current = payload.get("current", {})
        hourly = payload.get("hourly", {})
        precip_probs = hourly.get("precipitation_probability", [])
        precip_prob = precip_probs[0] if precip_probs else 0

        wind_speed = current.get("wind_speed_10m")
        wind_gusts = current.get("wind_gusts_10m")
        precipitation = current.get("precipitation")

        if wind_speed is None or wind_gusts is None:
            raise ValueError("Incomplete weather payload from Open-Meteo")

        return {
            "wind_speed_kmh": round(float(wind_speed), 1),
            "wind_gusts_kmh": round(float(wind_gusts), 1),
            "precipitation_probability": float(precip_prob or 0),
            "precipitation_mm": float(precipitation or 0),
            "source": "live",
            "provider": "Open-Meteo Weather API",
        }
    except Exception:
        demo = _load_demo()
        fallback = dict(demo["fallback_weather"][zone_key])
        fallback["source"] = "demo"
        fallback["provider"] = "Demo Reference Dataset (live API unavailable)"
        return fallback
