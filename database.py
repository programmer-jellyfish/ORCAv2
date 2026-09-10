"""
database.py
Thin Supabase PostgreSQL persistence layer.
Every function fails soft: if Supabase is not configured or unreachable,
the app keeps working and simply skips persistence.
"""

import os
from datetime import datetime, timezone

try:
    from supabase import create_client
except ImportError:
    create_client = None

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_client = None
_attempted = False


def get_client():
    global _client, _attempted
    if _client is not None:
        return _client
    if _attempted:
        return None
    _attempted = True
    if not (SUPABASE_URL and SUPABASE_KEY and create_client):
        return None
    try:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
        return _client
    except Exception:
        return None


def is_connected():
    return get_client() is not None


def _now():
    return datetime.now(timezone.utc).isoformat()


def sync_locations(zones):
    client = get_client()
    if not client:
        return False
    try:
        for key, z in zones.items():
            client.table("locations").upsert({
                "zone_key": key,
                "name": z["name"],
                "lat": z["lat"],
                "lon": z["lon"],
                "description": z.get("description", ""),
            }, on_conflict="zone_key").execute()
        return True
    except Exception:
        return False


def save_analysis_snapshot(zone_key, safety_score, fishing_score, recommendation_score, raw_data):
    client = get_client()
    if not client:
        return False
    try:
        client.table("analysis_snapshots").insert({
            "zone": zone_key,
            "safety_score": safety_score,
            "fishing_score": fishing_score,
            "recommendation_score": recommendation_score,
            "raw_data": raw_data,
            "created_at": _now(),
        }).execute()
        return True
    except Exception:
        return False


def save_chat_history(query_text, response_text, intent, language):
    client = get_client()
    if not client:
        return False
    try:
        client.table("chat_history").insert({
            "query": query_text,
            "response": response_text,
            "intent": intent,
            "language": language,
            "created_at": _now(),
        }).execute()
        return True
    except Exception:
        return False


def get_chat_history(limit=20):
    client = get_client()
    if not client:
        return []
    try:
        res = (
            client.table("chat_history")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []
    except Exception:
        return []
