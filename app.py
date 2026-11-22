import streamlit as st

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
                        f"{recommended['duration_min']} min"
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
                # ROUTE COMPARISON
                # =================================================

                st.subheader("🛣️ Route Comparison")

                for route in routes:

                    # Risk icon

                    if route["risk_level"] == "LOW":
                        risk_icon = "🟢"

                    elif route["risk_level"] == "MEDIUM":
                        risk_icon = "🟡"

                    else:
                        risk_icon = "🔴"

                    # Recommended marker

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
                            f"{route['duration_min']} min"
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