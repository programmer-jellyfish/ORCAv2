# ORCA
### Marine EcOsystem Reasoning with Collaborative Agents

ORCA is a marine intelligence dashboard prototype built for an ISRO-style
ocean and fisheries decision-support problem statement. It combines live
weather and marine data with deterministic scoring logic and a
collaborative multi-agent pipeline to answer questions like:

- Is it safe to go fishing?
- Which fishing zone is best? / Where's the nearest Potential Fishing Zone?
- Compare Zone A and Zone B
- What are current sea conditions?
- Why was a zone recommended?
- Are there any cyclone or lightning alerts?
- What's the safest route from Zone A to Zone B?

## What's new

This pass fixed the core conversational bug and added several genuinely
new capabilities beyond the original single-answer chatbot:

- **Fixed: identical answer for every query.** The old fallback narrator
  (used whenever `GEMINI_API_KEY` isn't configured — which is the state
  of the public demo deployment) ignored the detected intent and the
  zones actually being asked about, and always printed the same
  three-zone score dump. `gemini_service.py` is now intent-aware and
  focus-zone-aware, so "is it safe?", "compare A and B", "why this
  zone?", "any alerts?" and "plan a route" each produce genuinely
  different, relevant answers — with or without a live Gemini key.
- **Alert Agent** (`alert_agent.py`) — new pipeline stage that derives
  proactive high-wind, high-swell, and storm/lightning-risk advisories
  from live wind gust, wave height, and rain-probability thresholds.
  Surfaced as a banner in the UI and folded into every relevant answer.
- **Geofence Agent** (`geofence_agent.py`) — flags zones or route
  waypoints that fall within a configured warning radius of a
  restricted/sensitive boundary (demo data only — clearly labeled as
  illustrative, not an official maritime boundary).
- **Route Agent** (`route_agent.py`) — plans a route between two zones,
  computes distance and bearing, and automatically reroutes to the
  safest available zone if the requested destination is currently
  classified Unsafe.
- **Interactive geospatial map** — a Leaflet map (in `index.html` /
  `script.js`) now shows zone markers colour-coded by safety label,
  Potential Fishing Zone hotspots, geofence buffers, and any planned
  route, instead of only score cards and a table.
- **Multi-turn conversational memory** — the frontend now keeps the last
  few exchanges and sends them back on each request; `gemini_service.py`
  includes that history in the prompt so follow-up questions like
  "what about that zone?" have context.
- **New intents**: `pfz` (potential fishing zone lookup), `alerts`, and
  `route`, on top of the original five.

## Architecture

```
User Query
  -> Query Analyzer      (intent, language, zone + route-pair detection)
  -> Task Planner         (builds the visible execution pipeline)
  -> Weather Agent         (Open-Meteo Weather API: wind, rain)
  -> Ocean Agent            (Open-Meteo Marine API: waves, sea temp)
  -> Fishing Agent            (combines ocean data + chlorophyll reference)
  -> Risk Engine                (deterministic safety + fishing scores)
  -> Alert Agent                  (wind / swell / storm-risk hazard advisories)
  -> Geofence Agent                 (proximity to restricted / sensitive zones)
  -> Route Agent                      (only for routing queries; risk-aware rerouting)
  -> Recommendation Engine              (60% safety + 40% fishing potential)
  -> Gemini Explanation                   (narrates results only, never invents numbers)
```

Every score shown in the UI is computed by plain Python math in
`risk_engine.py` (safety/fishing scores), `alert_agent.py` (hazard
thresholds), `geofence_agent.py` (haversine distance checks), and
`route_agent.py` (distance/bearing + reroute logic). Gemini is only ever
given the final computed numbers and asked to explain them in natural
language (English or Tamil) — it cannot alter or invent a score. If
Gemini is unreachable, `gemini_service.py` falls back to a deterministic,
template-based explanation built from the same numbers and tailored to
the query's intent, so the app never breaks and never repeats itself.

## Stack

- **Backend:** Python + Flask
- **Frontend:** Plain HTML, CSS, JavaScript
- **Conversational layer:** Google Gemini API (explanation only)
- **Persistence:** Supabase PostgreSQL 
- **Weather data:** Open-Meteo Weather API
- **Marine data:** Open-Meteo Marine API

## File structure

All files live directly in the project root — there are no subfolders.

```
ORCA/
├── app.py                 Flask app + API routes
├── agents.py               Weather / Ocean / Fishing agents
├── alert_agent.py            Hazard advisory (wind/swell/storm-risk) agent
├── geofence_agent.py           Boundary-proximity checks (zones + routes)
├── route_agent.py                Risk-aware route planning between zones
├── query_analyzer.py               Intent + language + route-pair detection
├── task_planner.py                   Builds the (intent-dependent) execution pipeline
├── risk_engine.py                      Deterministic scoring + recommendation
├── marine_api.py                         Open-Meteo Marine API client
├── weather_api.py                          Open-Meteo Weather API client
├── database.py                               Supabase persistence (fails soft)
├── gemini_service.py                           Gemini explanation + intent-aware fallback
├── index.html                                    Dashboard markup (incl. Leaflet map)
├── style.css                                       Dashboard styling
├── script.js                                         Dashboard behaviour + map + memory
├── demo_data.json                                      Zones, PFZ points, geofence data
├── schema.sql                                            Supabase table definitions
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
└── README.md
```

## Demo zones

Three fixed demo zones are used (off the Tamil Nadu coast, Bay of Bengal):

| Zone | Character                                             |
|------|--------------------------------------------------------|
| A    | Balanced coastal waters — stable wind/wave, moderate fishing potential |
| B    | Nutrient-rich offshore waters — best fishing potential, but poor safety (high wind & swell) |
| C    | Sheltered southern belt — calmer seas, lower biological activity |

With current demo/live data, Zone A typically wins the final
recommendation because it best balances safety and fishing potential,
even though Zone B scores higher on fishing potential alone.

**Note on chlorophyll:** Open-Meteo does not provide chlorophyll or
ocean-color data. Chlorophyll concentration is therefore supplied as a
clearly labeled demo reference value per zone (`chlorophyll_source:
"demo-reference"` in the API response) and used only as an ecological
proxy input to the fishing-potential score. No component of the UI
claims this is live satellite data.

## Running locally

```bash
cd ORCA
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in GEMINI_API_KEY / SUPABASE_* if available
python app.py
```

Then open `http://localhost:5000`.

The app works fully even with an empty `.env` file:
- Without `GEMINI_API_KEY`, explanations use the Python fallback narrator.
- Without `SUPABASE_URL` / `SUPABASE_KEY`, the app runs in offline mode
  and simply skips persistence.
- If Open-Meteo APIs are unreachable, `demo_data.json` fallback values
  are used and labeled as demo data in the UI.

## Supabase setup (optional)

1. Create a Supabase project.
2. Run `schema.sql` in the Supabase SQL editor.
3. Copy your project URL and API key into `.env` as `SUPABASE_URL` and
   `SUPABASE_KEY`.

## Deploying to Vercel

The project is ready to deploy as-is:

```bash
vercel
```

`vercel.json` routes all requests to `app.py`, which Vercel's
`@vercel/python` builder treats as a WSGI application (the module-level
`app` Flask instance). Add your environment variables
(`GEMINI_API_KEY`, `GEMINI_MODEL`, `SUPABASE_URL`, `SUPABASE_KEY`) in the
Vercel project settings before deploying.

## Design notes

The UI intentionally avoids maps, GIS libraries, emojis, gradients, and
glassmorphism. It uses a dark navy/slate base with a single restrained
cyan accent, monospace type for data and scores, and a card-based layout
suited to a scientific / mission-control style review by technical
evaluators.
