import pydeck as pdk
import streamlit as st

from backend import analyze_route


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="AI Road Risk Analyzer",
    page_icon="🛣️",
    layout="wide",
)

st.title("🛣️ AI Road Risk Analyzer")
st.markdown(
    "### Find a lower-risk route, not just the fastest route.\n\n"
    "Compare real route options, see exactly which roads each route follows, "
    "and view the AI risk recommendation."
)
st.divider()


# =========================================================
# INPUTS
# =========================================================

col1, col2 = st.columns(2)
with col1:
    start_location = st.text_input(
        "📍 Starting Location",
        placeholder="Example: Bangalore",
    )
with col2:
    destination = st.text_input(
        "🎯 Destination",
        placeholder="Example: Mysore",
    )

analyze_button = st.button(
    "🔍 Analyze Routes",
    type="primary",
    use_container_width=True,
)


# =========================================================
# MAP HELPERS
# =========================================================

ROUTE_COLORS = {
    1: [45, 120, 220, 230],   # blue
    2: [230, 145, 35, 230],   # orange
    3: [145, 95, 190, 230],   # purple
}
RECOMMENDED_COLOR = [20, 155, 85, 245]  # green


def build_route_map(routes, recommended, selected_route_number):
    """Draw the actual OSRM paths; widen the route currently being inspected."""
    path_data = []
    endpoint_data = []
    all_points = []

    for route in routes:
        path = route.get("geometry") or []
        if len(path) < 2:
            continue

        route_number = route["route_number"]
        is_recommended = route_number == recommended["route_number"]
        is_selected = route_number == selected_route_number

        color = (
            RECOMMENDED_COLOR
            if is_recommended
            else ROUTE_COLORS.get(route_number, [100, 100, 100, 220])
        )

        path_data.append({
            "path": path,
            "color": color,
            "width": 8 if is_selected else 4,
            "label": (
                f"Route {route_number} — AI recommended"
                if is_recommended
                else f"Route {route_number}"
            ),
        })
        all_points.extend(path)

    if not path_data or not all_points:
        return None

    # All alternatives returned for a given request share the same endpoints.
    first_path = routes[0].get("geometry") or []
    if len(first_path) >= 2:
        endpoint_data = [
            {
                "position": first_path[0],
                "label": "START",
                "color": [20, 145, 75, 255],
            },
            {
                "position": first_path[-1],
                "label": "DESTINATION",
                "color": [205, 55, 55, 255],
            },
        ]

    selected = next(
        (r for r in routes if r["route_number"] == selected_route_number),
        recommended,
    )
    selected_distance = selected["distance_km"]
    if selected_distance < 60:
        zoom = 9
    elif selected_distance < 150:
        zoom = 8
    elif selected_distance < 350:
        zoom = 6.5
    elif selected_distance < 800:
        zoom = 5.5
    else:
        zoom = 4.5

    # Use the selected route to center the map rather than unrelated route points.
    focus_points = selected.get("geometry") or all_points
    center_lon = sum(point[0] for point in focus_points) / len(focus_points)
    center_lat = sum(point[1] for point in focus_points) / len(focus_points)

    layers = [
        pdk.Layer(
            "PathLayer",
            data=path_data,
            get_path="path",
            get_color="color",
            get_width="width",
            width_min_pixels=3,
            pickable=True,
        ),
        pdk.Layer(
            "ScatterplotLayer",
            data=endpoint_data,
            get_position="position",
            get_fill_color="color",
            get_radius=850,
            radius_min_pixels=7,
            radius_max_pixels=13,
            pickable=True,
        ),
        pdk.Layer(
            "TextLayer",
            data=endpoint_data,
            get_position="position",
            get_text="label",
            get_size=14,
            get_color=[35, 35, 35, 255],
            get_alignment_baseline="bottom",
            get_pixel_offset=[0, -12],
            pickable=False,
        ),
    ]

    return pdk.Deck(
        layers=layers,
        initial_view_state=pdk.ViewState(
            latitude=center_lat,
            longitude=center_lon,
            zoom=zoom,
            pitch=0,
        ),
        map_style="light",
        tooltip={"text": "{label}"},
    )


def display_directions(route):
    directions = route.get("directions") or []

    if not directions:
        st.info(
            "Turn-by-turn instructions were not provided for this route. "
            "Use the highlighted route line and road list to identify its path."
        )
        return

    for step_number, step in enumerate(directions, start=1):
        instruction = step.get("instruction", "Continue")
        distance_text = step.get("distance") or ""
        if distance_text:
            st.write(f"{step_number}. **{instruction}** — {distance_text}")
        else:
            st.write(f"{step_number}. **{instruction}**")


def show_route_legend(routes, recommended):
    """Show a precise Route-number-to-map-colour key."""
    legend_parts = []
    for route in routes:
        number = route["route_number"]
        color = (
            RECOMMENDED_COLOR
            if number == recommended["route_number"]
            else ROUTE_COLORS.get(number, [100, 100, 100, 255])
        )
        color_css = f"rgba({color[0]}, {color[1]}, {color[2]}, 1)"
        label = f"Route {number}"
        if number == recommended["route_number"]:
            label += " — AI recommended"
        legend_parts.append(
            f"<span style='white-space:nowrap;margin-right:18px;'>"
            f"<span style='color:{color_css};font-weight:900;'>━━</span> {label}</span>"
        )
    st.markdown("".join(legend_parts), unsafe_allow_html=True)


# =========================================================
# RUN ANALYSIS AND SAVE RESULTS FOR THE ROUTE SELECTOR
# =========================================================

if "route_analysis" not in st.session_state:
    st.session_state.route_analysis = None
if "analyzed_start" not in st.session_state:
    st.session_state.analyzed_start = ""
if "analyzed_destination" not in st.session_state:
    st.session_state.analyzed_destination = ""

if analyze_button:
    if not start_location.strip() or not destination.strip():
        st.warning("Please enter both starting location and destination.")
    elif start_location.strip().casefold() == destination.strip().casefold():
        st.warning("Starting location and destination must be different.")
    else:
        with st.spinner("🗺️ Finding actual routes and analysing road risk..."):
            try:
                new_result = analyze_route(start_location, destination)
                st.session_state.route_analysis = new_result
                st.session_state.analyzed_start = start_location.strip()
                st.session_state.analyzed_destination = destination.strip()
            except Exception as error:
                st.session_state.route_analysis = None
                st.error("❌ Unable to analyze the route.")
                st.exception(error)


# =========================================================
# DISPLAY STORED ANALYSIS
# =========================================================

result = st.session_state.route_analysis

if result:
    routes = result["routes"]
    recommended = result["recommended_route"]

    st.caption(
        f"Showing route analysis: {st.session_state.analyzed_start} → "
        f"{st.session_state.analyzed_destination}"
    )

    st.success(
        f"🏆 AI Recommendation: Route {recommended['route_number']} "
        f"has the lowest predicted risk among the "
        f"{len(routes)} actual route option(s) returned."
    )

    # -----------------------------------------------------
    # RECOMMENDED ROUTE SUMMARY
    # -----------------------------------------------------

    st.subheader("🏆 Recommended Route")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Distance", f"{recommended['distance_km']} km")
    with c2:
        st.metric("Travel Time", f"{recommended['duration_min']:.0f} min")
    with c3:
        st.metric("Estimated Traffic", recommended["traffic_label"])
    with c4:
        st.metric("Approx. Toll", f"₹{recommended['toll']}")

    st.write(f"🧭 **Main roads:** {recommended['route_description']}")
    st.write(f"🛣️ **Estimated Road Condition:** {recommended['road_condition_label']}")
    st.write(
        f"⚠️ **AI Road Risk:** {recommended['risk_score']}/100 "
        f"({recommended['risk_level']})"
    )
    st.progress(int(recommended["risk_score"]))

    st.caption(
        "Route paths, distances and travel times come from OSRM routing data. "
        "Traffic, road condition and toll are prototype estimates, not live verified measurements."
    )

    st.divider()

    # -----------------------------------------------------
    # ROUTE IDENTIFICATION: MAP + ROUTE SELECTOR
    # -----------------------------------------------------

    st.subheader("🗺️ Which road should I take?")
    st.write(
        "Each route number below is drawn on the map with its own colour. "
        "Select Route 1, Route 2 or Route 3 to highlight that exact path and view its directions."
    )

    route_numbers = [route["route_number"] for route in routes]

    def route_selector_label(number):
        if number == recommended["route_number"]:
            return f"Route {number} — AI recommended (lowest predicted risk)"
        return f"Route {number} — alternative"

    selected_route_number = st.selectbox(
        "Choose a route to see exactly which way it goes:",
        options=route_numbers,
        index=route_numbers.index(recommended["route_number"]),
        format_func=route_selector_label,
        key="route_path_selector_v2",
    )
    selected_route = next(
        route for route in routes
        if route["route_number"] == selected_route_number
    )

    route_map = build_route_map(
        routes,
        recommended,
        selected_route_number,
    )
    if route_map is not None:
        st.pydeck_chart(route_map, use_container_width=True)
        show_route_legend(routes, recommended)
        st.caption(
            f"Route {selected_route_number} is shown with a thicker line. "
            "The green line always marks the AI-recommended route. "
            "START and DESTINATION markers show the journey endpoints."
        )
    else:
        st.warning("The routing service did not return map geometry for these routes.")

    st.markdown(f"### 🧭 Exact path for Route {selected_route_number}")
    st.write(f"**Main roads / highways:** {selected_route['route_description']}")
    st.write(
        f"**Distance:** {selected_route['distance_km']} km  |  "
        f"**Travel time:** {selected_route['duration_min']:.0f} min"
    )

    with st.expander(
        f"View step-by-step driving directions for Route {selected_route_number}",
        expanded=True,
    ):
        display_directions(selected_route)

    st.divider()

    # -----------------------------------------------------
    # ROUTE COMPARISON
    # -----------------------------------------------------

    st.subheader("🛣️ Route Comparison")
    for route in routes:
        is_best = route["route_number"] == recommended["route_number"]
        heading = f"Route {route['route_number']}"
        if is_best:
            heading += " 🏆 AI RECOMMENDED"

        with st.container(border=True):
            st.markdown(f"### {heading}")
            r1, r2, r3, r4 = st.columns(4)
            with r1:
                st.metric("Distance", f"{route['distance_km']} km")
            with r2:
                st.metric("Travel Time", f"{route['duration_min']:.0f} min")
            with r3:
                st.metric("Estimated Traffic", route["traffic_label"])
            with r4:
                st.metric("Approx. Toll", f"₹{route['toll']}")

            st.write(f"🧭 **Main roads:** {route['route_description']}")
            st.write(f"🛣️ **Road Condition:** {route['road_condition_label']}")
            st.write(
                f"⚠️ **AI Road Risk:** {route['risk_score']}/100 "
                f"— {route['risk_level']}"
            )
            st.progress(int(route["risk_score"]))

    st.divider()

    # -----------------------------------------------------
    # AI EXPLANATION (PRESERVED)
    # -----------------------------------------------------

    st.subheader("🧠 AI Risk Analysis")
    st.info(
        "The trained Random Forest model evaluates each actual route using distance, "
        "travel time, estimated traffic, estimated road condition and approximate toll. "
        "The route with the lowest predicted risk score is recommended."
    )

    st.subheader("🤖 Why this route?")
    st.write(
        f"Route {recommended['route_number']} has the lowest predicted risk score "
        f"({recommended['risk_score']}/100) among the {len(routes)} actual route(s) "
        "returned by the routing service. Its highlighted path and driving directions "
        "are shown above so the user can identify which roads to take."
    )

    st.caption(
        "This tool compares route risk; it is not a live navigation service. "
        "Use a navigation app for live traffic updates, closures and turn-by-turn rerouting."
    )


# =========================================================
# FOOTER
# =========================================================

st.divider()
st.caption(
    "AI Road Risk Analyzer • Actual route geometry and driving steps from OSRM • "
    "Risk prediction from a trained Random Forest model"
)
