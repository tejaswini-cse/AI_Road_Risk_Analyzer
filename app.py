import streamlit as st
import pydeck as pdk
import re
import time

from backend import analyze_route


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="AI Road Risk Analyzer",
    page_icon="🛣️",
    layout="wide"
)


# =========================================================
# ROUTE MAP
# =========================================================

def show_route_map(routes, recommended):

    st.subheader("🗺️ Actual Route Map")

    map_routes = []
    all_coordinates = []

    colors = {
        1: [50, 120, 220, 220],
        2: [230, 140, 40, 220],
        3: [145, 90, 200, 220]
    }

    for route in routes:

        # Do not draw estimated routes.
        if not route.get("real_route", False):
            continue

        geometry = route.get("geometry")

        if not isinstance(geometry, dict):
            continue

        coordinates = geometry.get("coordinates", [])

        if not isinstance(coordinates, list):
            continue

        valid_coordinates = []

        for point in coordinates:

            if not isinstance(point, (list, tuple)):
                continue

            if len(point) < 2:
                continue

            try:
                longitude = float(point[0])
                latitude = float(point[1])
            except (TypeError, ValueError):
                continue

            valid_coordinates.append([
                longitude,
                latitude
            ])

        if len(valid_coordinates) < 2:
            continue

        route_number = route["route_number"]

        is_recommended = (
            route_number == recommended["route_number"]
        )

        if is_recommended:
            route_color = [20, 170, 85, 255]
            line_width = 8
        else:
            route_color = colors.get(
                route_number,
                [100, 100, 100, 220]
            )
            line_width = 5

        map_routes.append({
            "route_number": route_number,
            "route_name": (
                f"Route {route_number}"
                + (
                    " - AI Recommended"
                    if is_recommended else ""
                )
            ),
            "path": valid_coordinates,
            "color": route_color,
            "line_width": line_width
        })

        all_coordinates.extend(valid_coordinates)

    if not map_routes:

        st.warning(
            "The routing service did not return an actual "
            "route path for this search. Your AI route "
            "comparison is still available below."
        )

        return

    # =====================================================
    # MAP CENTER
    # =====================================================

    longitudes = [
        point[0] for point in all_coordinates
    ]

    latitudes = [
        point[1] for point in all_coordinates
    ]

    center_longitude = (
        min(longitudes) + max(longitudes)
    ) / 2

    center_latitude = (
        min(latitudes) + max(latitudes)
    ) / 2

    span = max(
        max(longitudes) - min(longitudes),
        max(latitudes) - min(latitudes)
    )

    if span > 4:
        zoom = 5
    elif span > 2:
        zoom = 6
    elif span > 1:
        zoom = 7
    elif span > 0.5:
        zoom = 8
    else:
        zoom = 9

    # =====================================================
    # DRAW ROUTES
    # =====================================================

    path_layer = pdk.Layer(
        "PathLayer",
        data=map_routes,
        get_path="path",
        get_color="color",
        get_width="line_width",
        width_units="pixels",
        width_min_pixels=3,
        width_max_pixels=10,
        pickable=True,
        auto_highlight=True
    )

    # =====================================================
    # START AND DESTINATION MARKERS
    # =====================================================

    first_path = map_routes[0]["path"]

    endpoint_data = [
        {
            "name": "Starting Location",
            "position": first_path[0],
            "color": [20, 160, 80, 255]
        },
        {
            "name": "Destination",
            "position": first_path[-1],
            "color": [220, 50, 50, 255]
        }
    ]

    endpoint_layer = pdk.Layer(
        "ScatterplotLayer",
        data=endpoint_data,
        get_position="position",
        get_fill_color="color",
        get_radius=600,
        radius_min_pixels=6,
        radius_max_pixels=12,
        pickable=True
    )

    view_state = pdk.ViewState(
        latitude=center_latitude,
        longitude=center_longitude,
        zoom=zoom,
        pitch=0
    )

    deck = pdk.Deck(
        layers=[
            path_layer,
            endpoint_layer
        ],
        initial_view_state=view_state,
        map_style=(
            "https://basemaps.cartocdn.com/"
            "gl/positron-gl-style/style.json"
        ),
        tooltip={
            "html": "<b>{route_name}</b><b>{name}</b>",
            "style": {
                "backgroundColor": "#222222",
                "color": "white"
            }
        }
    )

    st.pydeck_chart(
        deck,
        use_container_width=True
    )

    st.caption(
        "🟢 Green = AI recommended route | "
        "Other colours = alternative actual routes. "
        "Hover over a route to identify it."
    )

    # =====================================================
    # CHECK RECOMMENDED ROUTE
    # =====================================================

    recommended_is_mapped = any(
        item["route_number"]
        == recommended["route_number"]
        for item in map_routes
    )

    if recommended_is_mapped:

        st.success(
            f"Follow the green highlighted path: "
            f"Route {recommended['route_number']} "
            f"is recommended by the AI."
        )

    else:

        st.warning(
            f"Route {recommended['route_number']} is "
            "recommended by the risk calculation, but "
            "its actual road geometry is unavailable. "
            "The map only displays verified route paths."
        )


# =========================================================
# START ROUTE NAVIGATION
# =========================================================

def start_route_navigation(recommended):

    geometry = recommended.get("geometry")

    if not isinstance(geometry, dict):

        st.warning(
            "Navigation is not available for this route."
        )

        return

    coordinates = geometry.get("coordinates", [])

    if not isinstance(coordinates, list):

        st.warning(
            "Navigation path is not available."
        )

        return

    valid_coordinates = []

    for point in coordinates:

        if not isinstance(point, (list, tuple)):
            continue

        if len(point) < 2:
            continue

        try:

            longitude = float(point[0])
            latitude = float(point[1])

        except (TypeError, ValueError):

            continue

        valid_coordinates.append([
            longitude,
            latitude
        ])

    if len(valid_coordinates) < 2:

        st.warning(
            "Navigation path is not available."
        )

        return

    st.subheader("🧭 Route Navigation")

    st.info(
        f"🚗 Starting navigation on "
        f"Route {recommended['route_number']}"
    )

    navigation_map = st.empty()

    progress_bar = st.progress(
        0,
        text="Starting route..."
    )

    # =====================================================
    # CALCULATE MAP CENTER
    # =====================================================

    longitudes = [
        point[0]
        for point in valid_coordinates
    ]

    latitudes = [
        point[1]
        for point in valid_coordinates
    ]

    center_longitude = (
        min(longitudes) + max(longitudes)
    ) / 2

    center_latitude = (
        min(latitudes) + max(latitudes)
    ) / 2

    span = max(
        max(longitudes) - min(longitudes),
        max(latitudes) - min(latitudes)
    )

    if span > 4:
        zoom = 5
    elif span > 2:
        zoom = 6
    elif span > 1:
        zoom = 7
    elif span > 0.5:
        zoom = 8
    else:
        zoom = 9

    # =====================================================
    # ANIMATION
    # =====================================================

    total_steps = 80

    for step in range(total_steps):

        progress = step / (total_steps - 1)

        current_index = int(
            progress * (len(valid_coordinates) - 1)
        )

        current_position = valid_coordinates[
            current_index
        ]

        # =================================================
        # GREEN RECOMMENDED ROUTE
        # =================================================

        route_data = [
            {
                "path": valid_coordinates,
                "color": [20, 170, 85, 255]
            }
        ]

        route_layer = pdk.Layer(
            "PathLayer",
            data=route_data,
            get_path="path",
            get_color="color",
            get_width=8,
            width_units="pixels",
            width_min_pixels=4,
            width_max_pixels=10
        )

        # =================================================
        # MOVING VEHICLE
        # =================================================

        vehicle_data = [
            {
                "position": current_position
            }
        ]

        vehicle_layer = pdk.Layer(
            "ScatterplotLayer",
            data=vehicle_data,
            get_position="position",
            get_fill_color=[30, 100, 220, 255],
            get_radius=900,
            radius_min_pixels=8,
            radius_max_pixels=16,
            pickable=True
        )

        # =================================================
        # MAP
        # =================================================

        view_state = pdk.ViewState(
            latitude=center_latitude,
            longitude=center_longitude,
            zoom=zoom,
            pitch=0
        )

        deck = pdk.Deck(
            layers=[
                route_layer,
                vehicle_layer
            ],
            initial_view_state=view_state,
            map_style=(
                "https://basemaps.cartocdn.com/"
                "gl/positron-gl-style/style.json"
            ),
            tooltip={
                "html": "🚗 Current Location",
                "style": {
                    "backgroundColor": "#222222",
                    "color": "white"
                }
            }
        )

        navigation_map.pydeck_chart(
            deck,
            use_container_width=True
        )

        # =================================================
        # PROGRESS
        # =================================================

        percentage = int(
            progress * 100
        )

        progress_bar.progress(
            percentage,
            text=f"🚗 Route progress: {percentage}%"
        )

        time.sleep(0.08)

    progress_bar.progress(
        100,
        text="🏁 Arrived at destination"
    )

    st.success(
        f"🏁 Route {recommended['route_number']} "
        "navigation completed."
    )


# =========================================================
# HEADER
# =========================================================

st.title("🛣️ AI Road Risk Analyzer")

st.markdown(
    """
    ### Find the safest route, not just the fastest route.

    Compare available routes using **traffic, toll, road condition
    and AI-powered road risk analysis**.
    """
)

st.divider()


# =========================================================
# LOCATION INPUT
# =========================================================

col1, col2 = st.columns(2)

with col1:

    start_location = st.text_input(
        "📍 Starting Location",
        placeholder="Example: Bangalore"
    )

with col2:

    destination = st.text_input(
        "🎯 Destination",
        placeholder="Example: Mysore"
    )


# =========================================================
# ANALYZE BUTTON
# =========================================================

analyze_button = st.button(
    "🔍 Analyze Routes",
    type="primary",
    use_container_width=True
)


# =========================================================
# ROUTE ANALYSIS
# =========================================================

if analyze_button:

    if not start_location or not destination:

        st.warning(
            "Please enter both starting location and destination."
        )

    else:

        with st.spinner(
            "🤖 AI is comparing available routes..."
        ):

            try:

                result = analyze_route(
                    start_location,
                    destination
                )

                routes = result["routes"]
                recommended = result["recommended_route"]

                # =================================================
                # BEST ROUTE
                # =================================================

                st.success(
                    f"🏆 Best Route: Route "
                    f"{recommended['route_number']}"
                )

                st.markdown(
                    f"""
                    **AI Recommendation**

                    Route {recommended['route_number']} has the
                    lowest estimated road-risk score among the
                    available routes.
                    """
                )

                # =================================================
                # BEST ROUTE METRICS
                # =================================================

                st.subheader("🏆 Recommended Route")

                c1, c2, c3, c4 = st.columns(4)

                with c1:

                    st.metric(
                        "Distance",
                        f"{recommended['distance_km']} km"
                    )

                with c2:

                    st.metric(
                        "Travel Time",
                        f"{int(recommended['duration_min'] // 60)} hr "
                        f"{int(recommended['duration_min'] % 60)} min"
                    )

                with c3:

                    st.metric(
                        "Traffic",
                        recommended["traffic_label"]
                    )

                with c4:

                    st.metric(
                        "Toll",
                        f"₹{recommended['toll']}"
                    )

                st.write(
                    f"🛣️ **Road Condition:** "
                    f"{recommended['road_condition_label']}"
                )

                st.write(
                    f"⚠️ **AI Road Risk:** "
                    f"{recommended['risk_score']}/100 "
                    f"({recommended['risk_level']})"
                )

                st.progress(
                    int(recommended["risk_score"])
                )

                st.divider()

                # =================================================
                # ROUTE MAP
                # =================================================

                try:

                    show_route_map(
                        routes,
                        recommended
                    )

                except Exception:

                    st.warning(
                        "The route map could not be displayed. "
                        "Your AI route analysis is still available."
                    )

                # =================================================
                # START ROUTE
                # =================================================

                st.divider()

                if st.button(
                    "▶️ Start Route",
                    type="primary",
                    use_container_width=True
                ):

                    start_route_navigation(
                        recommended
                    )

                st.divider()

                # =================================================
                # ROUTE COMPARISON
                # =================================================

                st.subheader("🛣️ Route Comparison")

                for route in routes:

                    if route["risk_level"] == "LOW":

                        risk_icon = "🟢"

                    elif route["risk_level"] == "MEDIUM":

                        risk_icon = "🟡"

                    else:

                        risk_icon = "🔴"

                    if (
                        route["route_number"]
                        == recommended["route_number"]
                    ):

                        title = (
                            f"### {risk_icon} Route "
                            f"{route['route_number']} "
                            f"🏆 RECOMMENDED"
                        )

                    else:

                        title = (
                            f"### {risk_icon} Route "
                            f"{route['route_number']}"
                        )

                    st.markdown(title)

                    r1, r2, r3, r4 = st.columns(4)

                    with r1:

                        st.metric(
                            "Distance",
                            f"{route['distance_km']} km"
                        )

                    with r2:

                        st.metric(
                            "Travel Time",
                            f"{int(route['duration_min'] // 60)} hr "
                            f"{int(route['duration_min'] % 60)} min"
                        )

                    with r3:

                        st.metric(
                            "Traffic",
                            route["traffic_label"]
                        )

                    with r4:

                        st.metric(
                            "Toll",
                            f"₹{route['toll']}"
                        )

                    st.write(
                        f"🛣️ **Road Condition:** "
                        f"{route['road_condition_label']}"
                    )

                    st.write(
                        f"⚠️ **AI Road Risk:** "
                        f"{route['risk_score']}/100 "
                        f"— {route['risk_level']}"
                    )

                    st.progress(
                        int(route["risk_score"])
                    )

                    st.divider()

                # =================================================
                # AI EXPLANATION
                # =================================================

                st.subheader("🧠 AI Risk Analysis")

                st.info(
                    """
                    The trained AI model evaluates each route using:

                    • 📏 Distance
                    • ⏱️ Travel time
                    • 🚗 Traffic level
                    • 🛣️ Road condition
                    • 💰 Toll estimate

                    A Random Forest model predicts the road-risk
                    score for each route. The route with the lowest
                    predicted risk is recommended.
                    """
                )

                # =================================================
                # WHY THIS ROUTE?
                # =================================================

                st.subheader("🤖 Why this route?")

                st.info(
                    f"""
                    **Route {recommended['route_number']}** is
                    currently recommended because it has the
                    lowest estimated road-risk score.

                    The AI considers:

                    • 🚗 Traffic
                    • 🛣️ Road condition
                    • 💰 Toll
                    • 📏 Distance
                    • ⏱️ Travel time

                    The goal is to identify a route that provides
                    a better balance between travel convenience
                    and road safety.
                    """
                )

            except Exception as e:

                st.error(
                    "❌ Unable to analyze the route."
                )

                st.exception(e)


# =========================================================
# FOOTER
# =========================================================

st.divider()

st.caption(
    "AI Road Risk Analyzer • AI-powered safer route comparison"
)
