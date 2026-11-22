import hashlib
import os

import joblib
import numpy as np
import requests


# =========================================================
# TRAINED AI MODEL
# =========================================================

MODEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "road_risk_model.joblib",
)

AI_MODEL = joblib.load(MODEL_PATH)


# =========================================================
# STABLE SEED FOR REPEATABLE PROTOTYPE ESTIMATES
# =========================================================

def stable_seed(start, destination):
    text = start.strip().lower() + "->" + destination.strip().lower()
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


# =========================================================
# GEOCODING - INDIA
# =========================================================

def geocode_location(location):
    location = location.strip()
    if not location:
        raise ValueError("Please enter a location.")

    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{location}, India",
        "format": "json",
        "limit": 1,
        "countrycodes": "in",
    }
    headers = {"User-Agent": "AI-Road-Risk-Analyzer/1.0"}

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if not data:
        raise ValueError(f"Location not found in India: {location}")

    return float(data[0]["lat"]), float(data[0]["lon"])


# =========================================================
# ROUTE INSTRUCTION HELPERS
# =========================================================

def get_road_label(step):
    """Build a recognizable road label from OSM road name/reference."""
    road_name = (step.get("name") or "").strip()
    road_ref = (step.get("ref") or "").strip()

    if road_ref and road_name and road_ref.casefold() not in road_name.casefold():
        return f"{road_ref} ({road_name})"
    return road_ref or road_name


def format_route_instruction(step):
    """Convert an OSRM maneuver step into a readable driving instruction."""
    maneuver = step.get("maneuver") or {}
    maneuver_type = (maneuver.get("type") or "continue").lower()
    modifier = (maneuver.get("modifier") or "").replace("_", " ").lower()
    road = get_road_label(step)

    if maneuver_type == "depart":
        instruction = "Start"
        if road:
            instruction += f" on {road}"
    elif maneuver_type == "arrive":
        instruction = "Arrive at your destination"
    elif maneuver_type in {"roundabout", "rotary"}:
        exit_number = maneuver.get("exit")
        instruction = (
            f"At the roundabout, take exit {exit_number}"
            if exit_number
            else "Enter the roundabout"
        )
        if road:
            instruction += f" onto {road}"
    elif maneuver_type in {"exit roundabout", "exit rotary"}:
        instruction = "Exit the roundabout"
        if road:
            instruction += f" onto {road}"
    else:
        action_text = {
            "turn": f"Turn {modifier}" if modifier else "Turn",
            "continue": "Continue",
            "new name": "Continue",
            "merge": "Merge",
            "fork": f"At the fork, keep {modifier}" if modifier else "Continue at the fork",
            "on ramp": "Take the ramp",
            "off ramp": "Take the exit ramp",
            "end of road": (
                f"At the end of the road, turn {modifier}"
                if modifier else "At the end of the road"
            ),
            "notification": "Continue",
            "use lane": "Follow the indicated lane",
        }
        instruction = action_text.get(maneuver_type, "Continue")
        if road:
            instruction += f" onto {road}"

    distance_m = float(step.get("distance") or 0)
    if distance_m >= 1000:
        distance_text = f"{distance_m / 1000:.1f} km"
    elif distance_m > 0:
        distance_text = f"{distance_m:.0f} m"
    else:
        distance_text = ""

    return {
        "instruction": instruction,
        "distance": distance_text,
        "distance_m": distance_m,
        "road": road,
    }


def extract_route_details(route):
    """Extract real OSRM geometry, recognizable road names and turn instructions."""
    geometry = route.get("geometry") or {}
    coordinates = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
    if not coordinates or len(coordinates) < 2:
        raise ValueError("The routing service returned a route without map geometry.")

    directions = []
    road_names = []
    seen_roads = set()

    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            direction = format_route_instruction(step)
            if direction["instruction"]:
                directions.append(direction)

            road = direction["road"]
            if road:
                key = road.casefold()
                if key not in seen_roads:
                    seen_roads.add(key)
                    road_names.append(road)

    if not road_names:
        for leg in route.get("legs", []):
            summary = (leg.get("summary") or "").strip()
            if summary and summary.casefold() not in seen_roads:
                seen_roads.add(summary.casefold())
                road_names.append(summary)

    route_description = (
        " → ".join(road_names[:10])
        if road_names
        else "Road names unavailable in OpenStreetMap data; see highlighted map path"
    )

    return {
        "geometry": coordinates,
        "directions": directions,
        "route_description": route_description,
    }


# =========================================================
# OSRM ROUTING - REQUEST FULL PATH AND DIRECTIONS
# =========================================================

def get_routes(start_lat, start_lon, end_lat, end_lon):
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{start_lon},{start_lat};{end_lon},{end_lat}"
    )
    params = {
        "alternatives": "true",
        "overview": "full",
        "steps": "true",
        "geometries": "geojson",
    }

    response = requests.get(url, params=params, timeout=35)
    response.raise_for_status()
    data = response.json()

    if data.get("code") != "Ok":
        raise ValueError(
            f"OSRM could not calculate this route ({data.get('code', 'unknown error')})."
        )

    return data.get("routes", [])


# =========================================================
# USE ONLY REAL ROUTES RETURNED BY OSRM
# =========================================================

def build_route_candidates(osrm_routes, seed=None):
    candidates = []

    for route in osrm_routes[:3]:
        details = extract_route_details(route)
        candidates.append({
            "distance": route["distance"],
            "duration": route["duration"],
            "real_route": True,
            "geometry": details["geometry"],
            "directions": details["directions"],
            "route_description": details["route_description"],
        })

    return candidates


# =========================================================
# TRAFFIC ESTIMATION - PROTOTYPE ESTIMATE, NOT LIVE TRAFFIC
# =========================================================

def estimate_traffic(route, route_index, seed):
    distance_km = route["distance"] / 1000
    duration_hours = route["duration"] / 3600
    speed = 60 if duration_hours <= 0 else distance_km / duration_hours

    if speed >= 60:
        base = 1
    elif speed >= 45:
        base = 2
    elif speed >= 30:
        base = 3
    elif speed >= 20:
        base = 4
    else:
        base = 5

    rng = np.random.default_rng(seed + 500 + route_index)
    adjustment = int(rng.choice([-1, 0, 0, 1]))
    return max(1, min(5, base + adjustment))


def traffic_label(level):
    labels = {
        1: "Low (estimated)",
        2: "Moderate (estimated)",
        3: "High (estimated)",
        4: "Very High (estimated)",
        5: "Severe (estimated)",
    }
    return labels[level]


# =========================================================
# ROAD CONDITION ESTIMATION - PROTOTYPE ESTIMATE
# =========================================================

def estimate_road_condition(route, route_index, seed):
    distance_km = route["distance"] / 1000
    rng = np.random.default_rng(seed + 1000 + route_index)
    distance_factor = min(2, int(distance_km / 150))
    random_component = int(rng.integers(1, 4))
    condition = random_component + distance_factor
    return max(1, min(5, condition))


def road_condition_label(level):
    labels = {
        1: "Very Good (estimated)",
        2: "Good (estimated)",
        3: "Average (estimated)",
        4: "Poor (estimated)",
        5: "Very Poor (estimated)",
    }
    return labels[level]


# =========================================================
# TOLL ESTIMATION - APPROXIMATE, NOT LIVE PLAZA PRICING
# =========================================================

def estimate_toll(route, route_index, seed):
    distance_km = route["distance"] / 1000

    if distance_km < 40:
        base = 0
    elif distance_km < 80:
        base = 50
    elif distance_km < 120:
        base = 100
    elif distance_km < 180:
        base = 150
    elif distance_km < 250:
        base = 200
    else:
        base = 250

    rng = np.random.default_rng(seed + 1500 + route_index)
    adjustment = int(rng.choice([-50, 0, 0, 50]))
    return max(0, base + adjustment)


# =========================================================
# AI ROAD RISK
# =========================================================

def calculate_risk(distance_km, duration_min, traffic, road_condition, toll):
    features = np.array([[
        distance_km,
        duration_min,
        traffic,
        road_condition,
        toll,
    ]])

    ai_prediction = AI_MODEL.predict(features)[0]
    traffic_effect = (traffic - 1) * 5
    road_effect = (road_condition - 1) * 7
    time_effect = min(10, duration_min / 30)

    final_score = (
        ai_prediction * 0.55
        + traffic_effect
        + road_effect
        + time_effect
    )
    return round(float(max(0, min(100, final_score))), 1)


def risk_level(score):
    if score < 30:
        return "LOW"
    if score < 60:
        return "MEDIUM"
    return "HIGH"


# =========================================================
# MAIN ROUTE ANALYSIS
# =========================================================

def analyze_route(start_location, destination):
    seed = stable_seed(start_location, destination)

    start_lat, start_lon = geocode_location(start_location)
    end_lat, end_lon = geocode_location(destination)

    osrm_routes = get_routes(start_lat, start_lon, end_lat, end_lon)
    if not osrm_routes:
        raise ValueError("No routes were found between these locations.")

    candidates = build_route_candidates(osrm_routes, seed)
    if not candidates:
        raise ValueError("No usable road routes were returned by OSRM.")

    analyzed_routes = []

    for index, route in enumerate(candidates):
        distance_km = route["distance"] / 1000
        duration_min = route["duration"] / 60

        traffic = estimate_traffic(route, index, seed)
        road_condition = estimate_road_condition(route, index, seed)
        toll = estimate_toll(route, index, seed)

        risk_score = calculate_risk(
            distance_km,
            duration_min,
            traffic,
            road_condition,
            toll,
        )

        analyzed_routes.append({
            "route_number": index + 1,
            "distance_km": round(distance_km, 1),
            "duration_min": round(duration_min, 1),
            "traffic": traffic,
            "traffic_label": traffic_label(traffic),
            "road_condition": road_condition,
            "road_condition_label": road_condition_label(road_condition),
            "toll": toll,
            "risk_score": risk_score,
            "risk_level": risk_level(risk_score),
            "real_route": True,
            "geometry": route["geometry"],
            "directions": route["directions"],
            "route_description": route["route_description"],
        })

    recommended_route = min(
        analyzed_routes,
        key=lambda route: route["risk_score"],
    )

    return {
        "routes": analyzed_routes,
        "recommended_route": recommended_route,
    }
