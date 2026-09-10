// ORCA frontend logic - vanilla JS, no frameworks.

const PIPELINE_STEPS_DEFAULT = [
  { step: "Query Analyzer", description: "Interpreting intent, language, and zone references" },
  { step: "Task Planner", description: "Building the agent execution plan" },
  { step: "Weather Agent", description: "Retrieving wind, gusts, and precipitation data" },
  { step: "Ocean Agent", description: "Retrieving wave height, wave period, and sea temperature" },
  { step: "Fishing Agent", description: "Combining ocean data with fishing indicators" },
  { step: "Risk Engine", description: "Computing deterministic safety and fishing scores" },
  { step: "Alert Agent", description: "Checking wind, swell, and storm-risk thresholds for hazards" },
  { step: "Geofence Agent", description: "Checking zones against restricted / sensitive boundaries" },
  { step: "Recommendation Engine", description: "Ranking zones and selecting the best balance" },
  { step: "Gemini Explanation", description: "Generating a natural language explanation" },
];

const UI_TEXT = {
  en: {
    placeholder: "Ask ORCA about fishing safety, zones, alerts, routes, or sea conditions...",
    send: "Analyze",
    thinking: "Analyzing conditions across all zones...",
    baseline: "Baseline snapshot across all monitored zones",
    afterQuery: "Latest analysis based on your query",
    recommended: "Recommended",
    demoLabel: "Demo",
    liveLabel: "Live",
    noAlerts: "No active hazard alerts in any monitored zone at this time.",
  },
  ta: {
    placeholder: "மீன்பிடி பாதுகாப்பு, மண்டலங்கள், எச்சரிக்கைகள், பாதைகள் அல்லது கடல் நிலைமைகள் பற்றி ORCA-விடம் கேளுங்கள்...",
    send: "பகுப்பாய்வு",
    thinking: "அனைத்து மண்டலங்களிலும் நிலைமைகளை பகுப்பாய்வு செய்கிறது...",
    baseline: "கண்காணிக்கப்படும் அனைத்து மண்டலங்களின் அடிப்படை தரவு",
    afterQuery: "உங்கள் கேள்வியின் அடிப்படையிலான சமீபத்திய பகுப்பாய்வு",
    recommended: "பரிந்துரைக்கப்படுகிறது",
    demoLabel: "டெமோ",
    liveLabel: "நேரடி",
    noAlerts: "இந்த நேரத்தில் எந்த மண்டலத்திலும் செயலில் உள்ள அபாய எச்சரிக்கைகள் இல்லை.",
  },
};

let state = {
  language: "en",
  history: [],       // [{query, answer}], sent back to the server for multi-turn context
  map: null,
  mapLayers: [],
  pfzPoints: [],
  geofenceBoundaries: [],
};

document.addEventListener("DOMContentLoaded", () => {
  renderPipeline(PIPELINE_STEPS_DEFAULT, null);
  wireUI();
  loadStatus();
  loadBaselineZones();
});

function wireUI() {
  document.getElementById("btnEnglish").addEventListener("click", () => setLanguage("en"));
  document.getElementById("btnTamil").addEventListener("click", () => setLanguage("ta"));

  document.getElementById("queryForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("queryInput");
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    handleQuery(text);
  });

  document.querySelectorAll(".suggested-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const q = btn.getAttribute("data-query");
      handleQuery(q);
    });
  });
}

function setLanguage(lang) {
  state.language = lang;
  document.getElementById("btnEnglish").classList.toggle("active", lang === "en");
  document.getElementById("btnTamil").classList.toggle("active", lang === "ta");
  document.getElementById("queryInput").placeholder = UI_TEXT[lang].placeholder;
  document.getElementById("sendBtn").textContent = UI_TEXT[lang].send;
}

// ---------------- Status header ----------------

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    setDot("dotWeather", data.weather_api === "operational" ? "ok" : "err");
    setDot("dotMarine", data.marine_api === "operational" ? "ok" : "err");
    setDot("dotGemini", data.gemini === "configured" ? "ok" : "warn");
    setDot("dotSupabase", data.supabase === "connected" ? "ok" : "warn");
  } catch (err) {
    ["dotWeather", "dotMarine", "dotGemini", "dotSupabase"].forEach((id) => setDot(id, "err"));
  }
}

function setDot(id, cls) {
  const el = document.getElementById(id);
  el.classList.remove("ok", "warn", "err");
  el.classList.add(cls);
}

// ---------------- Pipeline rendering ----------------

function renderPipeline(steps, activeIndex) {
  const list = document.getElementById("pipelineList");
  list.innerHTML = "";
  steps.forEach((step, idx) => {
    const li = document.createElement("li");
    if (activeIndex === null) {
      // idle state, nothing highlighted
    } else if (activeIndex === -1) {
      li.classList.add("done"); // finalized, all steps completed
    } else if (idx < activeIndex) {
      li.classList.add("done");
    } else if (idx === activeIndex) {
      li.classList.add("active");
    }
    li.innerHTML = `
      <span class="step-index">${String(idx + 1).padStart(2, "0")}</span>
      <span class="step-marker"></span>
      <span class="step-text">
        <span class="step-name">${step.step}</span>
        <span class="step-desc">${step.description}</span>
      </span>
    `;
    list.appendChild(li);
  });
}

async function animatePipeline() {
  for (let i = 0; i < PIPELINE_STEPS_DEFAULT.length; i++) {
    renderPipeline(PIPELINE_STEPS_DEFAULT, i);
    await sleep(120);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ---------------- Chat ----------------

function appendMessage(role, text, badge) {
  const log = document.getElementById("chatLog");
  const div = document.createElement("div");
  div.className = `chat-message ${role}`;
  const roleLabel = role === "user" ? "You" : "ORCA";
  div.innerHTML = `
    <div class="message-role">${roleLabel}</div>
    <div class="message-body">${escapeHtml(text)}</div>
    ${badge ? `<div class="message-badge">${badge}</div>` : ""}
  `;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.innerText = str;
  return d.innerHTML;
}

async function handleQuery(text) {
  appendMessage("user", text);
  document.getElementById("sendBtn").disabled = true;

  const pipelinePromise = animatePipeline();

  try {
    const res = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: text,
        language: state.language,
        history: state.history.slice(-6),
      }),
    });

    await pipelinePromise;

    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      appendMessage("assistant", errBody.error || "The request could not be processed. Please try again.");
      return;
    }

    const data = await res.json();

    // Finalize the pipeline view with the *actual* backend-computed plan
    // (step count / labels vary by intent - e.g. Route Agent only appears
    // for routing queries).
    if (data.pipeline && data.pipeline.length) {
      renderPipeline(data.pipeline, -1);
    }

    const badge = data.gemini_used
      ? `Explanation source: Gemini &middot; Persistence: ${data.supabase_connected ? "Supabase connected" : "offline mode"}`
      : `Explanation source: Gemini &middot; Persistence: ${data.supabase_connected ? "Supabase connected" : "offline mode"}`;

    appendMessage("assistant", data.explanation, badge);

    state.history.push({ query: text, answer: data.explanation });
    if (state.history.length > 10) state.history = state.history.slice(-10);

    renderResults(data.zones, data.recommendation, UI_TEXT[state.language].afterQuery);
    renderAlertsBanner(data.zones);
    renderRoute(data.route);
    updateMap(data.zones, data.route);
  } catch (err) {
    await pipelinePromise;
    appendMessage(
      "assistant",
      "ORCA could not reach the backend service. Please verify the server is running and try again."
    );
  } finally {
    document.getElementById("sendBtn").disabled = false;
  }
}

// ---------------- Results rendering ----------------

async function loadBaselineZones() {
  try {
    const res = await fetch("/api/zones");
    const data = await res.json();
    state.pfzPoints = data.pfz_points || [];
    state.geofenceBoundaries = data.geofence_boundaries || [];
    renderResults(data.zones, data.recommendation, UI_TEXT[state.language].baseline);
    renderAlertsBanner(data.zones);
    initMap(data.zones);
  } catch (err) {
    document.getElementById("resultsCaption").textContent =
      "Unable to load baseline zone data. Backend may be offline.";
  }
}

function renderResults(zones, recommendation, caption) {
  document.getElementById("resultsCaption").textContent = caption;
  const bestZone = zones.find((z) => z.zone === recommendation.best_zone) || zones[0];

  renderScoreCards(bestZone, recommendation);
  renderConditionsTable(zones);
  renderRecommendation(recommendation, zones);
  renderZoneComparison(zones, recommendation.best_zone);
}

function renderScoreCards(bestZone, recommendation) {
  const container = document.getElementById("scoreCards");
  container.innerHTML = `
    <div class="score-card">
      <div class="score-card-label">SAFETY SCORE &mdash; ZONE ${bestZone.zone}</div>
      <div class="score-card-value">${bestZone.safety_score}<span> / 100</span></div>
      <div class="tag ${safetyTagClass(bestZone.safety_label)}">${bestZone.safety_label}</div>
    </div>
    <div class="score-card">
      <div class="score-card-label">FISHING POTENTIAL &mdash; ZONE ${bestZone.zone}</div>
      <div class="score-card-value">${bestZone.fishing_score}<span> / 100</span></div>
      <div class="score-card-sub">Based on sea temperature, chlorophyll reference, and wave period</div>
    </div>
    <div class="score-card">
      <div class="score-card-label">RECOMMENDATION SCORE &mdash; ZONE ${bestZone.zone}</div>
      <div class="score-card-value">${bestZone.recommendation_score}<span> / 100</span></div>
      <div class="tag cyan">60% Safety + 40% Fishing Potential</div>
    </div>
  `;
}

function safetyTagClass(label) {
  if (label === "Safe") return "safe";
  if (label === "Caution") return "caution";
  return "unsafe";
}

function renderConditionsTable(zones) {
  const tbody = document.getElementById("conditionsTableBody");
  tbody.innerHTML = "";
  zones.forEach((z) => {
    const tr = document.createElement("tr");
    const weatherSource = z.weather.source;
    const oceanSource = z.ocean.source;
    const isLive = weatherSource === "live" && oceanSource === "live";
    tr.innerHTML = `
      <td class="zone-name-cell">Zone ${z.zone}</td>
      <td>${z.weather.wind_speed_kmh}</td>
      <td>${z.ocean.wave_height_m}</td>
      <td>${z.ocean.wave_period_s}</td>
      <td>${z.ocean.sea_surface_temperature_c}</td>
      <td>${z.weather.precipitation_probability}</td>
      <td><span class="source-badge ${isLive ? "live" : ""}">${isLive ? "Live" : "Demo / Partial"}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderRecommendation(recommendation, zones) {
  const box = document.getElementById("recommendationBox");
  const evidenceItems = recommendation.reasoning.map((r) => `<li>${r}</li>`).join("");
  box.innerHTML = `
    <div class="recommendation-headline">Recommended zone: <span class="cyan-text">Zone ${recommendation.best_zone}</span></div>
    <ul class="evidence-list">${evidenceItems}</ul>
  `;
}

function renderZoneComparison(zones, bestZoneKey) {
  const container = document.getElementById("zoneComparison");
  container.innerHTML = "";
  zones.forEach((z) => {
    const isBest = z.zone === bestZoneKey;
    const card = document.createElement("div");
    card.className = `zone-card ${isBest ? "recommended" : ""}`;
    card.innerHTML = `
      ${isBest ? `<div class="recommended-flag">RECOMMENDED</div>` : ""}
      <div class="zone-card-title">Zone ${z.zone}</div>
      <div class="zone-card-desc">${z.description}</div>
      <div class="zone-metric-row">
        <span class="zone-metric-label">Safety score</span>
        <span class="zone-metric-value">${z.safety_score} / 100</span>
      </div>
      <div class="zone-metric-row">
        <span class="zone-metric-label">Fishing potential</span>
        <span class="zone-metric-value">${z.fishing_score} / 100</span>
      </div>
      <div class="zone-metric-row">
        <span class="zone-metric-label">Recommendation score</span>
        <span class="zone-metric-value">${z.recommendation_score} / 100</span>
      </div>
      <div class="zone-metric-row">
        <span class="zone-metric-label">Wave height</span>
        <span class="zone-metric-value">${z.ocean.wave_height_m} m</span>
      </div>
      <div class="zone-metric-row">
        <span class="zone-metric-label">Wind speed</span>
        <span class="zone-metric-value">${z.weather.wind_speed_kmh} km/h</span>
      </div>
    `;
    container.appendChild(card);
  });
}

// ---------------- Alerts banner ----------------

function renderAlertsBanner(zones) {
  const banner = document.getElementById("alertsBanner");
  banner.innerHTML = "";
  const withAlerts = zones.filter((z) => z.alerts && z.alerts.length);
  if (!withAlerts.length) {
    return; // stays empty -> hidden via CSS :empty rule
  }
  withAlerts.forEach((z) => {
    z.alerts.forEach((a) => {
      const div = document.createElement("div");
      div.className = `alert-item ${a.severity}`;
      div.innerHTML = `
        <span class="alert-zone-tag">ZONE ${z.zone}</span>
        <span>${escapeHtml(a.message)}</span>
      `;
      banner.appendChild(div);
    });
  });
}

// ---------------- Route rendering ----------------

function renderRoute(route) {
  const section = document.getElementById("routeSection");
  const box = document.getElementById("routeBox");
  if (!route) {
    section.style.display = "none";
    return;
  }
  section.style.display = "block";
  let html = `
    <div class="route-headline">Zone ${route.final_start} &rarr; Zone ${route.final_end}
      &middot; ${route.distance_km} km &middot; bearing ${route.bearing_deg}&deg;</div>
  `;
  if (route.rerouted) {
    html += `<div class="route-reroute-note">Rerouted: ${escapeHtml(route.reroute_reason)}</div>`;
  }
  if (route.geofence_flags && route.geofence_flags.length) {
    route.geofence_flags.forEach((flag) => {
      flag.notices.forEach((n) => {
        html += `<div class="route-geofence-note">Zone ${flag.zone} waypoint is ${n.distance_km} km from
          "${escapeHtml(n.boundary_name)}" (warning radius ${n.warning_radius_km} km). ${escapeHtml(n.note)}</div>`;
      });
    });
  }
  box.innerHTML = html;
}

// ---------------- Map ----------------

function safetyColor(label) {
  if (label === "Safe") return "#4FAE7C";
  if (label === "Caution") return "#D0A244";
  return "#D0685E";
}

function initMap(zones) {
  if (typeof L === "undefined") return; // Leaflet failed to load (e.g. offline)
  if (state.map) return;

  const mapEl = document.getElementById("mapView");
  if (!mapEl) return;

  state.map = L.map(mapEl, { zoomControl: true, attributionControl: true }).setView([13.0, 80.45], 9);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 12,
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(state.map);

  updateMap(zones, null);
}

function clearMapLayers() {
  state.mapLayers.forEach((layer) => state.map.removeLayer(layer));
  state.mapLayers = [];
}

function updateMap(zones, route) {
  if (!state.map || typeof L === "undefined") return;
  clearMapLayers();

  // Zone markers, colored by safety label
  zones.forEach((z) => {
    const marker = L.circleMarker([z.lat, z.lon], {
      radius: 11,
      color: safetyColor(z.safety_label),
      fillColor: safetyColor(z.safety_label),
      fillOpacity: 0.75,
      weight: 2,
    }).addTo(state.map);
    marker.bindPopup(
      `<strong>Zone ${z.zone}</strong><br>${z.name}<br>Safety: ${z.safety_label} (${z.safety_score}/100)<br>` +
      `Fishing potential: ${z.fishing_score}/100` +
      (z.alerts && z.alerts.length ? `<br><em>${z.alerts.length} active alert(s)</em>` : "")
    );
    state.mapLayers.push(marker);
  });

  // PFZ hotspot markers
  (state.pfzPoints || []).forEach((p) => {
    const marker = L.circleMarker([p.lat, p.lon], {
      radius: 6,
      color: "#3FC6D1",
      fillColor: "#3FC6D1",
      fillOpacity: 0.9,
      weight: 1,
    }).addTo(state.map);
    marker.bindPopup(`<strong>${p.name}</strong><br>Potential Fishing Zone &middot; strength: ${p.strength}`);
    state.mapLayers.push(marker);
  });

  // Demo geofence buffers
  (state.geofenceBoundaries || []).forEach((b) => {
    const circle = L.circle([b.lat, b.lon], {
      radius: b.warning_radius_km * 1000,
      color: "#8FA4BA",
      weight: 1.5,
      dashArray: "4 4",
      fillOpacity: 0.03,
    }).addTo(state.map);
    circle.bindPopup(`<strong>${b.name}</strong><br>${b.note}`);
    state.mapLayers.push(circle);
  });

  // Route line, if present
  if (route && route.waypoints && route.waypoints.length >= 2) {
    const line = L.polyline(
      route.waypoints.map((w) => [w.lat, w.lon]),
      { color: "#3FC6D1", weight: 3, dashArray: route.rerouted ? "6 4" : null }
    ).addTo(state.map);
    state.mapLayers.push(line);
    state.map.fitBounds(line.getBounds().pad(0.4));
  }
}
