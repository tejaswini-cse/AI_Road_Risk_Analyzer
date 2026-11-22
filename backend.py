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
    "model",
    "road_risk_model.joblib"
)

AI_MODEL = joblib.load(MODEL_PATH)


# =========================================================
# STABLE SEED
# =========================================================

def stable_seed(start, destination):

    text = (
        start.strip().lower()
        + "->"
        + destination.strip().lower()
    )

    digest = hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()

    return int(digest[:8], 16)


# =========================================================
# GEOCODING
# =========================================================

def geocode_location(location):

    url = "https://nominatim.openstreetmap.org/search"

    params = {
        "q": location,
        "format": "json",
        "limit": 1
    }

    headers = {
        "User-Agent": "AI-Road-Risk-Analyzer/1.0"
    }

    response = requests.get(
        url,
        params=params,
        headers=headers,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        raise ValueError(
            f"Location not found: {location}"
        )

    return (
        float(data[0]["lat"]),
        float(data[0]["lon"])
    )


# =========================================================
# OSRM ROUTING
# =========================================================

def get_routes(
    start_lat,
    start_lon,
    end_lat,
    end_lon
):

    url = (
        "https://router.project-osrm.org/"
        "route/v1/driving/"
        f"{start_lon},{start_lat};"
        f"{end_lon},{end_lat}"
    )

    params = {
        "alternatives": "true",
        "overview": "false",
        "steps": "false"
    }

    response = requests.get(
        url,
        params=params,
        timeout=25
    )

    response.raise_for_status()

    data = response.json()

    if data.get("code") != "Ok":
        raise ValueError(
            "Could not calculate route."
        )

    return data.get("routes", [])


# =========================================================
# CREATE ROUTE CANDIDATES
# =========================================================

def build_route_candidates(
    osrm_routes,
    seed
):

    rng = np.random.default_rng(seed)

    # -----------------------------------------------------
    # 3 or more real routes
    # -----------------------------------------------------

    if len(osrm_routes) >= 3:

        return [
            {
                "distance": route["distance"],
                "duration": route["duration"],
                "real_route": True
            }

            for route in osrm_routes[:3]
        ]

    # -----------------------------------------------------
    # 2 real routes
    # -----------------------------------------------------

    if len(osrm_routes) == 2:

        base = osrm_routes[0]
        second = osrm_routes[1]

        estimated_distance = (
            base["distance"]
            * rng.uniform(1.05, 1.14)
        )

        estimated_duration = (
            base["duration"]
            * rng.uniform(1.08, 1.18)
        )

        return [

            {
                "distance": base["distance"],
                "duration": base["duration"],
                "real_route": True
            },

            {
                "distance": second["distance"],
                "duration": second["duration"],
                "real_route": True
            },

            {
                "distance": estimated_distance,
                "duration": estimated_duration,
                "real_route": False
            }

        ]

    # -----------------------------------------------------
    # Only 1 real route
    # -----------------------------------------------------

    base = osrm_routes[0]

    candidates = [

        {
            "distance": base["distance"],
            "duration": base["duration"],
            "real_route": True
        }

    ]

    # Alternative 2

    candidates.append({

        "distance":
            base["distance"]
            * rng.uniform(1.04, 1.10),

        "duration":
            base["duration"]
            * rng.uniform(1.05, 1.12),

        "real_route": False

    })

    # Alternative 3

    candidates.append({

        "distance":
            base["distance"]
            * rng.uniform(1.08, 1.17),

        "duration":
            base["duration"]
            * rng.uniform(1.09, 1.20),

        "real_route": False

    })

    return candidates


# =========================================================
# TRAFFIC ESTIMATION
# =========================================================

def estimate_traffic(
    route,
    route_index,
    seed
):

    distance_km = (
        route["distance"] / 1000
    )

    duration_hours = (
        route["duration"] / 3600
    )

    if duration_hours <= 0:

        speed = 60

    else:

        speed = (
            distance_km
            / duration_hours
        )

    # Estimate traffic from average route speed

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

    # Stable route-specific variation

    rng = np.random.default_rng(
        seed + 500 + route_index
    )

    adjustment = int(
        rng.choice(
            [-1, 0, 0, 1]
        )
    )

    return max(
        1,
        min(
            5,
            base + adjustment
        )
    )


def traffic_label(level):

    labels = {

        1: "Low",

        2: "Moderate",

        3: "High",

        4: "Very High",

        5: "Severe"

    }

    return labels[level]


# =========================================================
# ROAD CONDITION
# =========================================================

def estimate_road_condition(
    route,
    route_index,
    seed
):

    """
    Prototype road-condition estimate.

    1 = Very Good
    2 = Good
    3 = Average
    4 = Poor
    5 = Very Poor
    """

    distance_km = (
        route["distance"] / 1000
    )

    rng = np.random.default_rng(
        seed + 1000 + route_index
    )

    # Longer routes can have more variation

    distance_factor = min(
        2,
        int(distance_km / 150)
    )

    random_component = int(
        rng.integers(1, 4)
    )

    condition = (
        random_component
        + distance_factor
    )

    return max(
        1,
        min(
            5,
            condition
        )
    )


def road_condition_label(level):

    labels = {

        1: "Very Good",

        2: "Good",

        3: "Average",

        4: "Poor",

        5: "Very Poor"

    }

    return labels[level]


# =========================================================
# TOLL ESTIMATION
# =========================================================

def estimate_toll(
    route,
    route_index,
    seed
):

    distance_km = (
        route["distance"] / 1000
    )

    # Base toll estimate

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

    # Stable route-specific variation

    rng = np.random.default_rng(
        seed + 1500 + route_index
    )

    adjustment = int(
        rng.choice(
            [-50, 0, 0, 50]
        )
    )

    return max(
        0,
        base + adjustment
    )


# =========================================================
# AI ROAD RISK
# =========================================================

def calculate_risk(
    distance_km,
    duration_min,
    traffic,
    road_condition,
    toll
):

    # Features must be in the same order
    # used during model training.

    features = np.array([

        [
            distance_km,
            duration_min,
            traffic,
            road_condition,
            toll
        ]

    ])

    # Prediction from trained Random Forest

    ai_prediction = AI_MODEL.predict(
        features
    )[0]

    # Additional transparent safety weighting

    traffic_effect = (
        (traffic - 1) * 5
    )

    road_effect = (
        (road_condition - 1) * 7
    )

    time_effect = min(
        10,
        duration_min / 30
    )

    final_score = (

        ai_prediction * 0.55

        + traffic_effect

        + road_effect

        + time_effect

    )

    return round(

        float(

            max(
                0,
                min(
                    100,
                    final_score
                )
            )

        ),

        1

    )


# =========================================================
# RISK LEVEL
# =========================================================

def risk_level(score):

    if score < 30:

        return "LOW"

    elif score < 60:

        return "MEDIUM"

    return "HIGH"


# =========================================================
# MAIN ROUTE ANALYSIS
# =========================================================

def analyze_route(
    start_location,
    destination
):

    # -----------------------------------------------------
    # Stable seed
    # -----------------------------------------------------

    seed = stable_seed(
        start_location,
        destination
    )

    # -----------------------------------------------------
    # Geocode start
    # -----------------------------------------------------

    start_lat, start_lon = (
        geocode_location(
            start_location
        )
    )

    # -----------------------------------------------------
    # Geocode destination
    # -----------------------------------------------------

    end_lat, end_lon = (
        geocode_location(
            destination
        )
    )

    # -----------------------------------------------------
    # Get actual route information
    # -----------------------------------------------------

    osrm_routes = get_routes(
        start_lat,
        start_lon,
        end_lat,
        end_lon
    )

    if not osrm_routes:

        raise ValueError(
            "No routes were found."
        )

    # -----------------------------------------------------
    # Build route candidates
    # -----------------------------------------------------

    candidates = build_route_candidates(
        osrm_routes,
        seed
    )

    analyzed_routes = []

    # -----------------------------------------------------
    # Analyze every route
    # -----------------------------------------------------

    for index, route in enumerate(
        candidates
    ):

        distance_km = (
            route["distance"]
            / 1000
        )

        duration_min = (
            route["duration"]
            / 60
        )

        traffic = estimate_traffic(
            route,
            index,
            seed
        )

        road_condition = (
            estimate_road_condition(
                route,
                index,
                seed
            )
        )

        toll = estimate_toll(
            route,
            index,
            seed
        )

        risk_score = calculate_risk(
            distance_km,
            duration_min,
            traffic,
            road_condition,
            toll
        )

        analyzed_routes.append({

            "route_number":
                index + 1,

            "distance_km":
                round(
                    distance_km,
                    1
                ),

            "duration_min":
                round(
                    duration_min,
                    1
                ),

            "traffic":
                traffic,

            "traffic_label":
                traffic_label(
                    traffic
                ),

            "road_condition":
                road_condition,

            "road_condition_label":
                road_condition_label(
                    road_condition
                ),

            "toll":
                toll,

            "risk_score":
                risk_score,

            "risk_level":
                risk_level(
                    risk_score
                ),

            "real_route":
                route["real_route"]

        })

    # -----------------------------------------------------
    # AI recommendation
    # -----------------------------------------------------

    recommended_route = min(
        analyzed_routes,
        key=lambda route:
        route["risk_score"]
    )

    # -----------------------------------------------------
    # Return result
    # -----------------------------------------------------

    return {

        "routes":
            analyzed_routes,

        "recommended_route":
            recommended_route

    }