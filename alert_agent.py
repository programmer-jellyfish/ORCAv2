"""
alert_agent.py
Alert Agent - new pipeline stage.

Derives proactive hazard advisories (high wind, high swell, storm /
lightning risk) directly from the same weather and ocean numbers the
Risk Engine uses. Nothing here is invented: every alert is a threshold
rule applied to a real (or clearly-labeled demo) measurement, so the
agent is deterministic and auditable, just like risk_engine.py.

Storm / lightning risk is a heuristic proxy derived from rain
probability and wind gusts (Open-Meteo does not provide a direct
lightning-strike feed), and is always labeled as such - ORCA never
claims to have live lightning-detection data.
"""

WIND_GUST_SEVERE_KMH = 45.0
WIND_GUST_MODERATE_KMH = 32.0

WAVE_HEIGHT_SEVERE_M = 2.4
WAVE_HEIGHT_MODERATE_M = 1.6

STORM_RISK_SEVERE_PROB = 70.0
STORM_RISK_MODERATE_PROB = 45.0

CYCLONE_WATCH_GUST_KMH = 60.0

SEVERITY_RANK = {"severe": 3, "moderate": 2, "advisory": 1}


def evaluate_zone_alerts(zone_key, weather, ocean):
    """Returns a list of alert dicts for a single zone."""
    alerts = []
    gust = weather.get("wind_gusts_kmh", 0.0)
    wave = ocean.get("wave_height_m", 0.0)
    precip_prob = weather.get("precipitation_probability", 0.0)

    if gust >= CYCLONE_WATCH_GUST_KMH:
        alerts.append({
            "type": "cyclone_watch",
            "severity": "severe",
            "message": f"Sustained gusts of {gust} km/h are at cyclone-watch levels. Vessels should not put to sea.",
        })
    elif gust >= WIND_GUST_SEVERE_KMH:
        alerts.append({
            "type": "high_wind",
            "severity": "severe",
            "message": f"Wind gusts of {gust} km/h exceed the small-craft safety threshold ({WIND_GUST_SEVERE_KMH} km/h).",
        })
    elif gust >= WIND_GUST_MODERATE_KMH:
        alerts.append({
            "type": "high_wind",
            "severity": "moderate",
            "message": f"Wind gusts of {gust} km/h are elevated. Exercise caution, especially for small craft.",
        })

    if wave >= WAVE_HEIGHT_SEVERE_M:
        alerts.append({
            "type": "high_swell",
            "severity": "severe",
            "message": f"Wave height of {wave} m exceeds the safe small-craft threshold ({WAVE_HEIGHT_SEVERE_M} m).",
        })
    elif wave >= WAVE_HEIGHT_MODERATE_M:
        alerts.append({
            "type": "high_swell",
            "severity": "moderate",
            "message": f"Wave height of {wave} m is above typical calm-sea range. Expect a rougher ride.",
        })

    if precip_prob >= STORM_RISK_SEVERE_PROB:
        alerts.append({
            "type": "storm_risk",
            "severity": "severe",
            "message": (
                f"Rain probability of {precip_prob}% indicates a high heuristic risk of thunderstorm "
                "activity and possible lightning (proxy estimate, not a direct lightning-detection feed)."
            ),
        })
    elif precip_prob >= STORM_RISK_MODERATE_PROB:
        alerts.append({
            "type": "storm_risk",
            "severity": "moderate",
            "message": (
                f"Rain probability of {precip_prob}% suggests a moderate heuristic risk of squalls. "
                "Monitor conditions before departure."
            ),
        })

    return alerts


def evaluate_all_alerts(evaluated_zones):
    """
    evaluated_zones: list of zone dicts already containing 'weather' and 'ocean'.
    Returns { zone_key: {"alerts": [...], "highest_severity": str|None} }
    """
    result = {}
    for z in evaluated_zones:
        alerts = evaluate_zone_alerts(z["zone"], z["weather"], z["ocean"])
        highest = None
        if alerts:
            highest = max(alerts, key=lambda a: SEVERITY_RANK.get(a["severity"], 0))["severity"]
        result[z["zone"]] = {"alerts": alerts, "highest_severity": highest}
    return result


def has_any_active_alert(alerts_by_zone):
    return any(v["alerts"] for v in alerts_by_zone.values())
