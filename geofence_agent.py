"""
geofence_agent.py
Geofence Agent - new pipeline stage.

Computes the great-circle distance from each monitored zone (and,
when relevant, a planned route) to a set of reference boundaries
defined in demo_data.json (geofence_boundaries), and raises a
proximity notice when a zone or waypoint falls inside the configured
warning radius.

IMPORTANT: the boundaries shipped in demo_data.json are explicitly
labeled as illustrative/demo-only. ORCA never presents them as an
official International Maritime Boundary Line or a substitute for
official Coast Guard / INCOIS notices - it only demonstrates how a
production system would wire in a real, licensed boundary dataset.
"""

import json
import math
import os

DEMO_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "demo_data.json")

with open(DEMO_DATA_PATH, "r", encoding="utf-8") as _f:
    _DEMO_DATA = json.load(_f)

BOUNDARIES = _DEMO_DATA.get("geofence_boundaries", [])


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def check_point(lat, lon):
    """Returns a list of proximity notices for a single lat/lon point."""
    notices = []
    for b in BOUNDARIES:
        dist = round(haversine_km(lat, lon, b["lat"], b["lon"]), 1)
        if dist <= b["warning_radius_km"]:
            notices.append({
                "boundary_id": b["id"],
                "boundary_name": b["name"],
                "kind": b["kind"],
                "distance_km": dist,
                "warning_radius_km": b["warning_radius_km"],
                "note": b["note"],
            })
    return notices


def evaluate_all_zones(zones_lookup):
    """
    zones_lookup: dict of zone_key -> {"lat":..., "lon":...}
    Returns { zone_key: [notice, ...] }
    """
    return {key: check_point(info["lat"], info["lon"]) for key, info in zones_lookup.items()}


def evaluate_route(waypoints):
    """
    waypoints: list of {"lat":..., "lon":..., "zone": ...}
    Returns list of {"zone":..., "notices": [...]} for waypoints that
    fall within a warning radius.
    """
    flagged = []
    for wp in waypoints:
        notices = check_point(wp["lat"], wp["lon"])
        if notices:
            flagged.append({"zone": wp.get("zone"), "lat": wp["lat"], "lon": wp["lon"], "notices": notices})
    return flagged
