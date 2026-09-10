"""
agents.py
Implements the Weather Agent, Ocean Agent, and Fishing Agent as simple,
composable Python functions. Each agent has one clear responsibility and
hands its output to the next stage of the pipeline (the Risk Engine).
"""

import os
import json

import weather_api
import marine_api

DEMO_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")

with open(DEMO_DATA_PATH, "r", encoding="utf-8") as _f:
    _DEMO_DATA = json.load(_f)

ZONES = _DEMO_DATA["zones"]
PFZ_POINTS = _DEMO_DATA.get("pfz_points", [])


def weather_agent(zone_key):
    """Retrieves wind / rain data for a zone."""
    zone = ZONES[zone_key]
    return weather_api.get_weather_data(zone_key, zone["lat"], zone["lon"])


def ocean_agent(zone_key):
    """Retrieves wave / sea-temperature data for a zone."""
    zone = ZONES[zone_key]
    return marine_api.get_marine_data(zone_key, zone["lat"], zone["lon"])


def fishing_agent(zone_key, ocean_data):
    """
    Combines live ocean data with chlorophyll reference data (chlorophyll
    concentration is not available from Open-Meteo, so a clearly labeled
    demo reference value is used as an ecological proxy input).
    """
    zone = ZONES[zone_key]
    return {
        "sea_surface_temperature_c": ocean_data["sea_surface_temperature_c"],
        "chlorophyll_mg_m3": zone["chlorophyll_mg_m3"],
        "wave_height_m": ocean_data["wave_height_m"],
        "wave_period_s": ocean_data["wave_period_s"],
        "chlorophyll_source": "demo-reference (not provided by Open-Meteo)",
    }


def run_zone_pipeline(zone_key):
    """Runs Weather Agent -> Ocean Agent -> Fishing Agent for one zone."""
    weather = weather_agent(zone_key)
    ocean = ocean_agent(zone_key)
    fishing_inputs = fishing_agent(zone_key, ocean)
    return {
        "zone": zone_key,
        "zone_info": ZONES[zone_key],
        "weather": weather,
        "ocean": ocean,
        "fishing_inputs": fishing_inputs,
    }
