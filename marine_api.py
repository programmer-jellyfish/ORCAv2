"""
marine_api.py
Fetches live wave height, wave period, and sea surface temperature from the
Open-Meteo Marine API. Falls back to labeled demo reference data if the API
is unreachable or returns an incomplete payload.
"""

import os
import json
import requests

DEMO_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")
MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
REQUEST_TIMEOUT = 6


def _load_demo():
    with open(DEMO_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_marine_data(zone_key, lat, lon):
    """
    Returns a dict with wave_height_m, wave_period_s, swell_wave_height_m,
    sea_surface_temperature_c, source, provider.
    """
    demo = _load_demo()
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "wave_height,wave_period,swell_wave_height,sea_surface_temperature",
            "timezone": "auto",
            "forecast_days": 1,
        }
        resp = requests.get(MARINE_URL, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        current = payload.get("current", {})

        wave_height = current.get("wave_height")
        wave_period = current.get("wave_period")
        swell_height = current.get("swell_wave_height")
        sst = current.get("sea_surface_temperature")

        if wave_height is None or wave_period is None:
            raise ValueError("Incomplete marine payload from Open-Meteo")

        sst_is_live = sst is not None
        if sst is None:
            sst = demo["fallback_marine"][zone_key]["sea_surface_temperature_c"]

        return {
            "wave_height_m": round(float(wave_height), 2),
            "wave_period_s": round(float(wave_period), 1),
            "swell_wave_height_m": round(float(swell_height), 2) if swell_height is not None else None,
            "sea_surface_temperature_c": round(float(sst), 1),
            "source": "live" if sst_is_live else "partial-demo",
            "provider": "Open-Meteo Marine API" if sst_is_live else
                        "Open-Meteo Marine API (sea temperature: demo reference)",
        }
    except Exception:
        fallback = dict(demo["fallback_marine"][zone_key])
        fallback["source"] = "demo"
        fallback["provider"] = "Demo Reference Dataset (live API unavailable)"
        return fallback
