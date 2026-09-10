"""
route_agent.py
Route Agent - new pipeline stage, used for "safest route" queries.

Builds a simple risk-aware route between two monitored zones. With
only three demo zones the "optimization" is intentionally transparent
rather than a black box: it computes the direct great-circle distance
and bearing, and if the requested destination zone currently carries
an "Unsafe" safety label it recommends diverting to the safest
available zone instead of silently routing into hazardous water -
mirroring how a production system would reroute around a live
hazard polygon.
"""

import math

from geofence_agent import haversine_km


def _bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    brng = (math.degrees(math.atan2(x, y)) + 360) % 360
    return round(brng, 1)


def plan_route(start_key, end_key, evaluated_by_zone):
    """
    evaluated_by_zone: dict zone_key -> evaluated zone dict (from risk_engine.evaluate_zone),
    each containing zone_info.lat/lon and safety_label/safety_score.
    """
    start = evaluated_by_zone[start_key]
    end = evaluated_by_zone[end_key]

    start_pt = start["zone_info"]
    end_pt = end["zone_info"]

    distance_km = round(haversine_km(start_pt["lat"], start_pt["lon"], end_pt["lat"], end_pt["lon"]), 1)
    bearing = _bearing(start_pt["lat"], start_pt["lon"], end_pt["lat"], end_pt["lon"])

    rerouted = False
    final_end_key = end_key
    reroute_reason = None

    if end["safety_label"] == "Unsafe":
        # Pick the safest of the remaining zones as an alternative destination.
        candidates = [z for k, z in evaluated_by_zone.items() if k != start_key]
        safest = max(candidates, key=lambda z: z["safety_score"])
        if safest["zone"] != end_key and safest["safety_label"] != "Unsafe":
            rerouted = True
            reroute_reason = (
                f"Zone {end_key} is currently classified Unsafe (safety score {end['safety_score']}/100), "
                f"so the route was diverted to Zone {safest['zone']} "
                f"(safety score {safest['safety_score']}/100) instead."
            )
            final_end_key = safest["zone"]
            end = safest
            end_pt = end["zone_info"]
            distance_km = round(haversine_km(start_pt["lat"], start_pt["lon"], end_pt["lat"], end_pt["lon"]), 1)
            bearing = _bearing(start_pt["lat"], start_pt["lon"], end_pt["lat"], end_pt["lon"])

    waypoints = [
        {"zone": start_key, "lat": start_pt["lat"], "lon": start_pt["lon"], "role": "origin"},
        {"zone": final_end_key, "lat": end_pt["lat"], "lon": end_pt["lon"], "role": "destination"},
    ]

    return {
        "requested_start": start_key,
        "requested_end": end_key,
        "final_start": start_key,
        "final_end": final_end_key,
        "rerouted": rerouted,
        "reroute_reason": reroute_reason,
        "distance_km": distance_km,
        "bearing_deg": bearing,
        "waypoints": waypoints,
        "destination_safety_label": end["safety_label"],
        "destination_safety_score": end["safety_score"],
    }
