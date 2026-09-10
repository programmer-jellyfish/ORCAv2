"""
gemini_service.py
Uses the Google Gemini API purely to EXPLAIN already-computed, deterministic
data in natural language (English or Tamil). Gemini is never allowed to
invent measurements or scores - it only receives the final numbers and
narrates them. If Gemini is unavailable, a Python-generated fallback
explanation is returned instead so the app keeps working.

FIX (was: identical answer for every query): the old fallback narrator
ignored `intent` and `focus_zones` entirely and always dumped the same
three-zone score listing regardless of what was asked. That meant that
whenever Gemini was not configured (e.g. no GEMINI_API_KEY on the public
deployment) every single query - "is it safe?", "compare zone A and B",
"why this zone?" - produced the exact same text. The fallback below is
now intent-aware, focuses on the zones actually relevant to the query,
and incorporates alerts / geofence / route data when present, so the
answer genuinely changes with the question even without a live Gemini
key. The same structured data is also what gets sent to Gemini itself,
so a configured deployment answers just as specifically.
"""

import os
import json

try:
    import google.generativeai as genai
except ImportError:
    genai = None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

_configured = False


def _ensure_configured():
    global _configured
    if not (GEMINI_API_KEY and genai):
        return False
    if not _configured:
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            _configured = True
        except Exception:
            return False
    return True


def _format_history(history):
    if not history:
        return "(no prior turns in this conversation)"
    lines = []
    for turn in history[-4:]:
        u = (turn.get("query") or "").strip()
        a = (turn.get("answer") or "").strip()
        if u:
            lines.append(f"User: {u}")
        if a:
            lines.append(f"ORCA: {a}")
    return "\n".join(lines) if lines else "(no prior turns in this conversation)"


def _build_prompt(query, intent, data, language, history=None):
    lang_instruction = (
        "Respond fully in Tamil, using clear, natural Tamil sentences."
        if language == "ta"
        else "Respond fully in English."
    )
    return f"""You are ORCA, a marine safety and fishing advisory assistant built for
a maritime intelligence dashboard reviewed by ISRO evaluators.

STRICT RULES YOU MUST FOLLOW:
1. Only explain, summarize, and interpret the numeric data given below.
2. Never invent, guess, or estimate any measurement, score, or statistic
   that is not explicitly present in the data.
3. If something needed to answer is missing from the data, say so plainly
   instead of making it up.
4. Focus your answer on what THIS query and its "focus_zones" actually
   ask about - do not recite every zone's full score breakdown unless
   the intent is compare_zones or the user asked for an overview.
5. If "alerts" contains active hazards, mention them - proactive safety
   warnings matter more than a complete score listing.
6. If "route" is present, answer primarily about the route (distance,
   bearing, any reroute, any geofence proximity).
7. Use the recent conversation turns below to stay consistent with
   anything already discussed, and to resolve references like "that
   zone" or "there" - but do not restate the whole prior conversation.
8. Keep the tone professional, precise, and concise (maximum 130 words).
9. {lang_instruction}
10. Do not use emojis or informal language.

Recent conversation (most recent last):
{_format_history(history)}

User query: "{query}"
Detected intent: {intent}

Calculated data (already computed deterministically by the system,
treat every number here as ground truth and do not alter it):
{json.dumps(data, indent=2, default=str)}

Write a short, professional explanation for the user based only on the
data above.
"""


def generate_explanation(query, intent, data, language="en", history=None):
    """
    Returns (explanation_text, used_gemini: bool)
    """
    if not _ensure_configured():
        return fallback_explanation(intent, data, language), False
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        prompt = _build_prompt(query, intent, data, language, history)
        response = model.generate_content(prompt)
        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise ValueError("Empty response from Gemini")
        return text, True
    except Exception:
        return fallback_explanation(intent, data, language), False


# ---------------------------------------------------------------------
# Deterministic, intent-aware fallback narrator
# ---------------------------------------------------------------------

def _zone_by_key(data, key):
    for z in data.get("zones", []):
        if z["zone"] == key:
            return z
    return None

def _focus_or_all(data):
    focus = data.get("focus_zones") or []
    zones = data.get("zones", [])
    if focus:
        picked = [z for z in zones if z["zone"] in focus]
        if picked:
            return picked
    return zones

def _alert_lines(data, language, zone_keys=None):
    alerts_by_zone = data.get("alerts_by_zone") or {}
    lines = []
    keys = zone_keys if zone_keys else list(alerts_by_zone.keys())
    for key in keys:
        info = alerts_by_zone.get(key)
        if not info or not info.get("alerts"):
            continue
        for a in info["alerts"]:
            prefix = ("எச்சரிக்கை" if language == "ta" else "Alert") + f" (Zone {key}, {a['severity']}): "
            lines.append(prefix + a["message"])
    return lines

def _geofence_lines(data, language, zone_keys=None):
    geofence_by_zone = data.get("geofence_by_zone") or {}
    lines = []
    keys = zone_keys if zone_keys else list(geofence_by_zone.keys())
    for key in keys:
        notices = geofence_by_zone.get(key) or []
        for n in notices:
            if language == "ta":
                lines.append(
                    f"மண்டலம் {key}, '{n['boundary_name']}' எல்லையிலிருந்து {n['distance_km']} கி.மீ தொலைவில் உள்ளது."
                )
            else:
                lines.append(
                    f"Zone {key} is {n['distance_km']} km from the '{n['boundary_name']}' boundary "
                    f"(warning radius {n['warning_radius_km']} km)."
                )
    return lines


def _route_lines(data, language):
    route = data.get("route")
    if not route:
        return []
    lines = []
    if language == "ta":
        lines.append(
            f"மண்டலம் {route['final_start']} முதல் மண்டலம் {route['final_end']} வரை தூரம் "
            f"{route['distance_km']} கி.மீ (திசை {route['bearing_deg']}\u00b0)."
        )
        if route.get("rerouted"):
            lines.append(route["reroute_reason"])
    else:
        lines.append(
            f"Route from Zone {route['final_start']} to Zone {route['final_end']}: "
            f"{route['distance_km']} km at a bearing of {route['bearing_deg']}\u00b0."
        )
        if route.get("rerouted"):
            lines.append(route["reroute_reason"])
    return lines


def _zone_line(z, language):
    if language == "ta":
        return (
            f"மண்டலம் {z['zone']}: பாதுகாப்பு {z['safety_score']}/100 ({z['safety_label']}), "
            f"மீன்பிடி திறன் {z['fishing_score']}/100, இறுதி மதிப்பெண் {z['recommendation_score']}/100."
        )
    return (
        f"Zone {z['zone']}: safety {z['safety_score']}/100 ({z['safety_label']}), "
        f"fishing potential {z['fishing_score']}/100, final score {z['recommendation_score']}/100."
    )


def fallback_explanation(intent, data, language):
    """
    Deterministic, template-based explanation used when Gemini is
    unavailable. Built only from the same numeric data Gemini would
    have received, so no information is fabricated - but, unlike the
    original version, it is intent-aware and focus-zone-aware so it
    does not repeat the same text for every kind of question.
    """
    recommended = data.get("recommended_zone")
    focus_zones = _focus_or_all(data)
    focus_keys = [z["zone"] for z in focus_zones]
    ta = language == "ta"

    header = (
        " "
        " "
        if ta else
        " "
        " "
    )

    lines = [header]

    if intent == "route":
        lines.extend(_route_lines(data, language))
        route = data.get("route") or {}
        end_key = route.get("final_end")
        if end_key:
            lines.extend(_geofence_lines(data, language, [route.get("final_start"), end_key]))
            lines.extend(_alert_lines(data, language, [end_key]))

    elif intent == "alerts":
        alert_lines = _alert_lines(data, language)
        if alert_lines:
            lines.extend(alert_lines)
        else:
            lines.append(
                "இந்த நேரத்தில் எந்த மண்டலத்திலும் செயலில் உள்ள அபாய எச்சரிக்கைகள் இல்லை." if ta
                else "No active hazard alerts in any monitored zone at this time."
            )

    elif intent == "compare_zones":
        for z in focus_zones:
            lines.append(_zone_line(z, language))
        if recommended:
            lines.append(
                f"பாதுகாப்பு மற்றும் மீன்பிடி வாய்ப்பை ஒப்பிட்டு, மண்டலம் {recommended} சிறந்தது." if ta
                else f"Comparing the two, Zone {recommended} currently offers the better overall balance."
            )

    elif intent == "explain_recommendation":
        target = _zone_by_key(data, recommended) or (focus_zones[0] if focus_zones else None)
        if target:
            lines.append(_zone_line(target, language))
            lines.append(
                f"இது 60% பாதுகாப்பு எடை மற்றும் 40% மீன்பிடி திறன் எடையுடன் கணக்கிடப்பட்டது." if ta
                else "This score is computed as 60% safety weight plus 40% fishing-potential weight."
            )
        lines.extend(_alert_lines(data, language, focus_keys))

    elif intent in ("best_zone", "pfz"):
        target = _zone_by_key(data, recommended)
        if target:
            lines.append(_zone_line(target, language))
        lines.extend(_alert_lines(data, language, [recommended] if recommended else None))

    elif intent == "safety_check":
        for z in focus_zones:
            if ta:
                lines.append(f"மண்டலம் {z['zone']}: பாதுகாப்பு நிலை - {z['safety_label']} ({z['safety_score']}/100).")
            else:
                lines.append(f"Zone {z['zone']}: safety status is {z['safety_label']} ({z['safety_score']}/100).")
        lines.extend(_alert_lines(data, language, focus_keys))

    elif intent == "current_conditions":
        for z in focus_zones:
            if ta:
                lines.append(
                    f"மண்டலம் {z['zone']}: காற்று {z['wind_speed_kmh']} கி.மீ/மணி, அலை உயரம் "
                    f"{z['wave_height_m']} மீ, கடல் வெப்பநிலை {z['sea_surface_temperature_c']}\u00b0C."
                )
            else:
                lines.append(
                    f"Zone {z['zone']}: wind {z['wind_speed_kmh']} km/h, wave height "
                    f"{z['wave_height_m']} m, sea surface temperature {z['sea_surface_temperature_c']}\u00b0C "
                    f"(source: {z['data_source']})."
                )
    else:  # general overview / query not understood
        lines.append(
            "இந்த கேள்வியை ORCA முழுமையாக புரிந்து கொள்ளவில்லை. கிடைக்கக்கூடிய பொதுவான தகவல் கீழே உள்ளது:" if ta
            else "ORCA couldn't fully interpret that query. Here's the general insight available right now:"
        )
        for z in focus_zones:
            lines.append(_zone_line(z, language))

    return " ".join(str(l) for l in lines if l)
