"""
task_planner.py
Second stage of the ORCA pipeline. Builds the ordered list of agent
steps that will be executed and displayed in the UI as the execution
pipeline. Weather / Ocean / Fishing / Risk / Alert / Geofence always
run because every query benefits from a current safety picture; the
Route Agent is inserted only for routing queries, and step
descriptions are tailored to the detected intent.
"""

BASE_PIPELINE = [
    {"step": "Query Analyzer", "description": "Interpreting intent, language, and zone references"},
    {"step": "Task Planner", "description": "Building the agent execution plan"},
    {"step": "Weather Agent", "description": "Retrieving wind, gusts, and precipitation data"},
    {"step": "Ocean Agent", "description": "Retrieving wave height, wave period, and sea temperature"},
    {"step": "Fishing Agent", "description": "Combining ocean data with fishing indicators"},
    {"step": "Risk Engine", "description": "Computing deterministic safety and fishing scores"},
    {"step": "Alert Agent", "description": "Checking wind, swell, and storm-risk thresholds for hazards"},
    {"step": "Geofence Agent", "description": "Checking zones against restricted / sensitive boundaries"},
    {"step": "Recommendation Engine", "description": "Ranking zones and selecting the best balance"},
    {"step": "Gemini Explanation", "description": "Generating a natural language explanation"},
]

ROUTE_STEP = {"step": "Route Agent", "description": "Planning a risk-aware route between the requested zones"}

INTENT_STEP_NOTES = {
    "compare_zones": {"Recommendation Engine": "Ranking the requested zones side by side"},
    "explain_recommendation": {"Gemini Explanation": "Explaining why the previous recommendation was made"},
    "best_zone": {"Recommendation Engine": "Selecting the single best zone by combined score"},
    "pfz": {"Fishing Agent": "Locating potential fishing zone hotspots by chlorophyll and sea temperature"},
    "safety_check": {"Risk Engine": "Focusing on safety score computation"},
    "current_conditions": {"Ocean Agent": "Focusing on live sea-state readings"},
    "alerts": {"Alert Agent": "Compiling all active hazard advisories across zones"},
    "route": {"Geofence Agent": "Checking the planned route against restricted boundaries"},
}


def build_plan(analysis):
    intent = analysis.get("intent", "general")
    overrides = INTENT_STEP_NOTES.get(intent, {})

    steps = list(BASE_PIPELINE)
    if intent == "route":
        # Insert the Route Agent right after Geofence Agent so the route
        # can be checked against boundaries once it is built.
        insert_at = next(i for i, s in enumerate(steps) if s["step"] == "Recommendation Engine")
        steps = steps[:insert_at] + [ROUTE_STEP] + steps[insert_at:]

    plan = []
    for item in steps:
        step_name = item["step"]
        plan.append({
            "step": step_name,
            "description": overrides.get(step_name, item["description"]),
            "status": "completed",
        })
    return plan
