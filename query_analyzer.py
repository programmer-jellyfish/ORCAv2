"""
query_analyzer.py
First stage of the ORCA pipeline. Classifies the user's natural language
query into a known intent, detects the response language, extracts any
zone letters (A / B / C) mentioned in the query, and - for routing
queries - identifies an origin/destination zone pair.
"""

import re

TAMIL_RANGE = re.compile(r"[\u0B80-\u0BFF]")
ZONE_PATTERN = re.compile(r"\bzone\s*([abc])\b", re.IGNORECASE)
ROUTE_PAIR_PATTERN = re.compile(
    r"from\s+zone\s*([abc]).{0,15}?\bto\s+zone\s*([abc])\b", re.IGNORECASE
)

KNOWN_INTENTS = [
    "compare_zones",
    "explain_recommendation",
    "best_zone",
    "pfz",
    "safety_check",
    "current_conditions",
    "alerts",
    "route",
    "general",
]


def detect_language(text, requested_language=None):
    if requested_language in ("en", "ta"):
        return requested_language
    if TAMIL_RANGE.search(text):
        return "ta"
    return "en"


def extract_zones(text):
    return sorted(set(m.group(1).upper() for m in ZONE_PATTERN.finditer(text)))


def extract_route_pair(text):
    m = ROUTE_PAIR_PATTERN.search(text)
    if m:
        return m.group(1).upper(), m.group(2).upper()
    return None


def analyze_query(text, requested_language=None):
    q = (text or "").lower().strip()
    language = detect_language(text or "", requested_language)
    zones_mentioned = extract_zones(text or "")
    route_pair = extract_route_pair(text or "")

    if route_pair or "route" in q or "navigat" in q or "safest way" in q or "path to" in q:
        intent = "route"
    elif "alert" in q or "cyclone" in q or "lightning" in q or "warning" in q or "hazard" in q:
        intent = "alerts"
    elif "compare" in q or " vs " in q or "versus" in q or len(zones_mentioned) >= 2:
        intent = "compare_zones"
    elif "why" in q or "reason" in q or "explain" in q:
        intent = "explain_recommendation"
    elif "pfz" in q or "potential fishing zone" in q or "chlorophyll" in q:
        intent = "pfz"
    elif "best" in q or "which zone" in q or "recommend" in q:
        intent = "best_zone"
    elif "safe" in q or "safety" in q or "go fishing" in q or "fishing today" in q or "venture" in q:
        intent = "safety_check"
    elif "condition" in q or "current sea" in q or "sea state" in q or "wave" in q or "weather" in q or "tide" in q:
        intent = "current_conditions"
    else:
        intent = "general"

    return {
        "raw_query": text,
        "intent": intent,
        "language": language,
        "zones_mentioned": zones_mentioned,
        "route_pair": route_pair,
    }
