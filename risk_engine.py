"""
risk_engine.py
All scoring in ORCA is deterministic Python math - Gemini never computes
or alters any of these numbers, it only explains them afterward.

Safety score combines wind, wave height, and rain probability.
Fishing potential combines sea surface temperature, chlorophyll, and
wave period (a proxy for sea-state favorability for fishing).
Final recommendation score = 60% safety + 40% fishing potential.
"""

SAFETY_WEIGHTS = {"wind": 0.4, "wave": 0.4, "rain": 0.2}
FISHING_WEIGHTS = {"sst": 0.4, "chlorophyll": 0.4, "wave_period": 0.2}
RECOMMENDATION_WEIGHTS = {"safety": 0.6, "fishing": 0.4}


def _clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def score_wind(wind_kmh):
    return _clamp(100 - wind_kmh * 2.5)


def score_wave_safety(wave_m):
    return _clamp(100 - wave_m * 40)


def score_rain(precip_prob):
    return _clamp(100 - precip_prob)


def calculate_safety_score(weather, ocean):
    wind_component = score_wind(weather["wind_speed_kmh"])
    wave_component = score_wave_safety(ocean["wave_height_m"])
    rain_component = score_rain(weather["precipitation_probability"])

    safety = (
        SAFETY_WEIGHTS["wind"] * wind_component
        + SAFETY_WEIGHTS["wave"] * wave_component
        + SAFETY_WEIGHTS["rain"] * rain_component
    )
    breakdown = {
        "wind_component": round(wind_component, 1),
        "wave_component": round(wave_component, 1),
        "rain_component": round(rain_component, 1),
    }
    return round(safety, 1), breakdown


def score_sst(sst):
    ideal_min, ideal_max = 26.0, 30.0
    if ideal_min <= sst <= ideal_max:
        return _clamp(100 - abs(28.0 - sst) * 2.5)
    distance = min(abs(sst - ideal_min), abs(sst - ideal_max))
    return _clamp(80 - distance * 10)


def score_chlorophyll(chl):
    return _clamp((chl / 3.0) * 100)


def score_wave_period(period):
    ideal_min, ideal_max = 6.0, 10.0
    if ideal_min <= period <= ideal_max:
        return _clamp(100 - abs(8.0 - period) * 5)
    return _clamp(70 - abs(period - 8.0) * 8)


def calculate_fishing_score(fishing_inputs):
    sst_component = score_sst(fishing_inputs["sea_surface_temperature_c"])
    chl_component = score_chlorophyll(fishing_inputs["chlorophyll_mg_m3"])
    period_component = score_wave_period(fishing_inputs["wave_period_s"])

    fishing = (
        FISHING_WEIGHTS["sst"] * sst_component
        + FISHING_WEIGHTS["chlorophyll"] * chl_component
        + FISHING_WEIGHTS["wave_period"] * period_component
    )
    breakdown = {
        "sst_component": round(sst_component, 1),
        "chlorophyll_component": round(chl_component, 1),
        "wave_period_component": round(period_component, 1),
    }
    return round(fishing, 1), breakdown


def calculate_recommendation_score(safety_score, fishing_score):
    score = (
        RECOMMENDATION_WEIGHTS["safety"] * safety_score
        + RECOMMENDATION_WEIGHTS["fishing"] * fishing_score
    )
    return round(score, 1)


def classify_safety(safety_score):
    if safety_score >= 70:
        return "Safe"
    if safety_score >= 45:
        return "Caution"
    return "Unsafe"


def evaluate_zone(zone_pipeline_result):
    weather = zone_pipeline_result["weather"]
    ocean = zone_pipeline_result["ocean"]
    fishing_inputs = zone_pipeline_result["fishing_inputs"]

    safety_score, safety_breakdown = calculate_safety_score(weather, ocean)
    fishing_score, fishing_breakdown = calculate_fishing_score(fishing_inputs)
    recommendation_score = calculate_recommendation_score(safety_score, fishing_score)

    return {
        "zone": zone_pipeline_result["zone"],
        "zone_info": zone_pipeline_result["zone_info"],
        "weather": weather,
        "ocean": ocean,
        "fishing_inputs": fishing_inputs,
        "safety_score": safety_score,
        "safety_breakdown": safety_breakdown,
        "safety_label": classify_safety(safety_score),
        "fishing_score": fishing_score,
        "fishing_breakdown": fishing_breakdown,
        "recommendation_score": recommendation_score,
    }


def rank_zones(evaluated_zones):
    return sorted(evaluated_zones, key=lambda z: z["recommendation_score"], reverse=True)


def recommend_best_zone(evaluated_zones):
    ranked = rank_zones(evaluated_zones)
    best = ranked[0]
    reasoning = []
    for z in ranked:
        reasoning.append(
            f"Zone {z['zone']}: recommendation score {z['recommendation_score']}/100 "
            f"(safety {z['safety_score']}/100 \u2014 {z['safety_label']}, "
            f"fishing potential {z['fishing_score']}/100)"
        )
    return {
        "best_zone": best["zone"],
        "ranked_zones": [z["zone"] for z in ranked],
        "reasoning": reasoning,
    }
