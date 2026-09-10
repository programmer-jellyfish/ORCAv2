"""
app.py
ORCA - Marine EcOsystem Reasoning with Collaborative Agents
Main Flask backend. Serves the flat frontend (index.html, style.css,
script.js) directly from the project root and exposes the JSON API that
drives the agent pipeline:

  Query -> Query Analyzer -> Task Planner -> Weather Agent -> Ocean Agent
        -> Fishing Agent -> Risk Engine -> Alert Agent -> Geofence Agent
        -> [Route Agent] -> Recommendation Engine -> Gemini Explanation
"""

import os
from flask import Flask, request, jsonify, send_from_directory

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import agents
import query_analyzer
import task_planner
import risk_engine
import alert_agent
import geofence_agent
import route_agent
import gemini_service
import database

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
ZONE_KEYS = ["A", "B", "C"]
MAX_HISTORY_TURNS = 6

app = Flask(__name__, static_folder=None)


# ---------------------------------------------------------------------
# Static frontend routes (flat structure - no /static or /templates)
# ---------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(ROOT_DIR, "index.html")


@app.route("/style.css")
def style_css():
    return send_from_directory(ROOT_DIR, "style.css")


@app.route("/script.js")
def script_js():
    return send_from_directory(ROOT_DIR, "script.js")


@app.route("/demo_data.json")
def demo_data_json():
    return send_from_directory(ROOT_DIR, "demo_data.json")


# ---------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------

def _evaluate_all_zones():
    evaluated = []
    for zone_key in ZONE_KEYS:
        pipeline_result = agents.run_zone_pipeline(zone_key)
        evaluated_zone = risk_engine.evaluate_zone(pipeline_result)
        evaluated.append(evaluated_zone)
        database.save_analysis_snapshot(
            zone_key,
            evaluated_zone["safety_score"],
            evaluated_zone["fishing_score"],
            evaluated_zone["recommendation_score"],
            {
                "weather": evaluated_zone["weather"],
                "ocean": evaluated_zone["ocean"],
                "fishing_inputs": evaluated_zone["fishing_inputs"],
            },
        )

    alerts_by_zone = alert_agent.evaluate_all_alerts(evaluated)
    geofence_by_zone = geofence_agent.evaluate_all_zones(
        {z["zone"]: {"lat": z["zone_info"]["lat"], "lon": z["zone_info"]["lon"]} for z in evaluated}
    )
    for z in evaluated:
        z["alerts"] = alerts_by_zone[z["zone"]]["alerts"]
        z["alert_severity"] = alerts_by_zone[z["zone"]]["highest_severity"]
        z["geofence_notices"] = geofence_by_zone[z["zone"]]

    return evaluated, alerts_by_zone, geofence_by_zone


def _serialize_zone(z):
    return {
        "zone": z["zone"],
        "name": z["zone_info"]["name"],
        "description": z["zone_info"]["description"],
        "lat": z["zone_info"]["lat"],
        "lon": z["zone_info"]["lon"],
        "weather": z["weather"],
        "ocean": z["ocean"],
        "fishing_inputs": z["fishing_inputs"],
        "safety_score": z["safety_score"],
        "safety_breakdown": z["safety_breakdown"],
        "safety_label": z["safety_label"],
        "fishing_score": z["fishing_score"],
        "fishing_breakdown": z["fishing_breakdown"],
        "recommendation_score": z["recommendation_score"],
        "alerts": z.get("alerts", []),
        "alert_severity": z.get("alert_severity"),
        "geofence_notices": z.get("geofence_notices", []),
    }


def _sanitize_history(raw_history):
    """Accepts client-supplied prior turns and trims/validates them."""
    if not isinstance(raw_history, list):
        return []
    clean = []
    for turn in raw_history[-MAX_HISTORY_TURNS:]:
        if not isinstance(turn, dict):
            continue
        q = str(turn.get("query", ""))[:400]
        a = str(turn.get("answer", ""))[:800]
        if q or a:
            clean.append({"query": q, "answer": a})
    return clean


# ---------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------

@app.route("/api/status")
def api_status():
    gemini_ok = bool(os.environ.get("GEMINI_API_KEY"))
    supabase_ok = database.is_connected()
    return jsonify({
        "weather_api": "operational",
        "marine_api": "operational",
        "gemini": "configured" if gemini_ok else "fallback-mode",
        "supabase": "connected" if supabase_ok else "offline-mode",
        "agents": [
            "Query Analyzer", "Task Planner", "Weather Agent", "Ocean Agent",
            "Fishing Agent", "Risk Engine", "Alert Agent", "Geofence Agent",
            "Route Agent", "Recommendation Engine", "Gemini Explanation",
        ],
    })


@app.route("/api/zones")
def api_zones():
    database.sync_locations(agents.ZONES)
    evaluated, alerts_by_zone, geofence_by_zone = _evaluate_all_zones()
    recommendation = risk_engine.recommend_best_zone(evaluated)
    return jsonify({
        "zones": [_serialize_zone(z) for z in evaluated],
        "recommendation": recommendation,
        "pfz_points": agents.PFZ_POINTS,
        "geofence_boundaries": geofence_agent.BOUNDARIES,
    })


@app.route("/api/history")
def api_history():
    return jsonify({"history": database.get_chat_history(20)})


@app.route("/api/query", methods=["POST"])
def api_query():
    body = request.get_json(force=True, silent=True) or {}
    user_query = (body.get("query") or "").strip()
    requested_language = body.get("language")
    conversation_history = _sanitize_history(body.get("history"))

    if not user_query:
        return jsonify({"error": "Query cannot be empty"}), 400

    # Stage 1: Query Analyzer
    analysis = query_analyzer.analyze_query(user_query, requested_language)

    # Stage 2: Task Planner
    plan = task_planner.build_plan(analysis)

    # Stage 3-8: Weather -> Ocean -> Fishing -> Risk -> Alert -> Geofence
    evaluated, alerts_by_zone, geofence_by_zone = _evaluate_all_zones()
    evaluated_by_zone = {z["zone"]: z for z in evaluated}

    # Stage 9: Recommendation Engine
    recommendation = risk_engine.recommend_best_zone(evaluated)

    zones_mentioned = analysis["zones_mentioned"] or []
    focus_zones = zones_mentioned if zones_mentioned else [recommendation["best_zone"]]

    # Optional Route Agent stage
    route_result = None
    if analysis["intent"] == "route":
        if analysis["route_pair"]:
            start_key, end_key = analysis["route_pair"]
        elif len(zones_mentioned) >= 2:
            start_key, end_key = zones_mentioned[0], zones_mentioned[1]
        else:
            # Default: treat the nearest sheltered zone as the origin and
            # the current recommended zone as the destination.
            start_key = "C" if recommendation["best_zone"] != "C" else "A"
            end_key = recommendation["best_zone"]
        route_result = route_agent.plan_route(start_key, end_key, evaluated_by_zone)
        route_result["geofence_flags"] = geofence_agent.evaluate_route(route_result["waypoints"])
        focus_zones = [route_result["final_start"], route_result["final_end"]]

    gemini_context = {
        "intent": analysis["intent"],
        "focus_zones": focus_zones,
        "recommended_zone": recommendation["best_zone"],
        "ranked_zones": recommendation["ranked_zones"],
        "zones": [
            {
                "zone": z["zone"],
                "safety_score": z["safety_score"],
                "safety_label": z["safety_label"],
                "fishing_score": z["fishing_score"],
                "recommendation_score": z["recommendation_score"],
                "wind_speed_kmh": z["weather"]["wind_speed_kmh"],
                "wave_height_m": z["ocean"]["wave_height_m"],
                "sea_surface_temperature_c": z["ocean"]["sea_surface_temperature_c"],
                "precipitation_probability": z["weather"]["precipitation_probability"],
                "data_source": z["weather"]["source"] + "/" + z["ocean"]["source"],
            }
            for z in evaluated
        ],
        "alerts_by_zone": alerts_by_zone,
        "geofence_by_zone": geofence_by_zone,
        "route": route_result,
    }

    # Stage 10: Gemini Explanation (never invents numbers, only narrates them)
    explanation_text, gemini_used = gemini_service.generate_explanation(
        user_query, analysis["intent"], gemini_context, analysis["language"], conversation_history
    )

    database.save_chat_history(user_query, explanation_text, analysis["intent"], analysis["language"])

    return jsonify({
        "analysis": analysis,
        "pipeline": plan,
        "zones": [_serialize_zone(z) for z in evaluated],
        "recommendation": recommendation,
        "route": route_result,
        "pfz_points": agents.PFZ_POINTS,
        "explanation": explanation_text,
        "gemini_used": gemini_used,
        "supabase_connected": database.is_connected(),
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
