"""
CODE TO ADD TO app.py FOR USER ACCOUNTS INTEGRATION

This file shows the code snippets to add to app.py to enable user accounts.

Add these sections in the order shown below.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Add imports at the top of app.py (after existing imports)
# ═══════════════════════════════════════════════════════════════════════════════

"""
# Add after existing imports
from auth.auth_manager import AuthManager
from auth.roi_calculator import ROICalculator
from db.postgres import check_connection, get_db
from models.user import User, UserPass, Trip, TripDay, FavoriteResort, UserSeasonStats
from datetime import timedelta
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Initialize session state for user (add after existing session state)
# ═══════════════════════════════════════════════════════════════════════════════

"""
# Add after: if "agent" not in st.session_state:
if "user" not in st.session_state:
    st.session_state.user = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Login/Register UI (add BEFORE the main UI code)
# ═══════════════════════════════════════════════════════════════════════════════

"""
# ── User Authentication ───────────────────────────────────────────────────────

# Check if database is available
db_available = check_connection()

if db_available and st.session_state.user is None:
    st.markdown("### 🔐 Colorado Powracle")
    st.caption("Sign in to track your trips and calculate pass ROI")

    tab1, tab2 = st.tabs(["Login", "Register"])

    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                success, message, user = AuthManager.login(email, password)
                if success:
                    st.session_state.user = user
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

    with tab2:
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_username = st.text_input("Username", key="reg_username")
            reg_password = st.text_input("Password", type="password", key="reg_password",
                                        help="Minimum 8 characters")
            reg_home = st.selectbox("Home City", list(_STARTING_CITIES.keys()), key="reg_home")

            submitted = st.form_submit_button("Create Account", use_container_width=True)

            if submitted:
                success, message, user = AuthManager.register_user(
                    email=reg_email,
                    username=reg_username,
                    password=reg_password,
                    home_city=reg_home
                )
                if success:
                    st.success(message + " Please login.")
                else:
                    st.error(message)

    # Guest mode option
    st.markdown("---")
    if st.button("Continue as Guest (limited features)", use_container_width=True):
        st.session_state.user = "guest"
        st.rerun()

    st.stop()  # Don't render main app until logged in
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Add navigation sidebar (at the start of the main UI)
# ═══════════════════════════════════════════════════════════════════════════════

"""
# Add before: col_left, col_right = st.columns([1, 1.5], gap="large")

with st.sidebar:
    if st.session_state.user and st.session_state.user != "guest":
        st.markdown(f"### 👤 {st.session_state.user.username}")
        st.caption(f"📍 {st.session_state.user.home_city}")

        st.markdown("---")

        # Navigation
        page = st.radio(
            "Navigation",
            ["🏠 Home", "👤 Profile", "🗓️ My Trips", "📊 Season Stats", "⚙️ Settings"],
            key="nav_radio"
        )
        st.session_state.current_page = page.split()[1]  # Extract page name

        st.markdown("---")

        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.current_page = "Home"
            st.rerun()
    else:
        st.markdown("### Guest Mode")
        st.caption("Limited features")

# Route to pages
if st.session_state.current_page != "Home":
    # Import and render specific page
    if st.session_state.current_page == "Profile":
        # Render profile page
        show_profile_page()
        st.stop()
    elif st.session_state.current_page == "Trips":
        show_trips_page()
        st.stop()
    elif st.session_state.current_page == "Stats":
        show_stats_page()
        st.stop()
    elif st.session_state.current_page == "Settings":
        show_settings_page()
        st.stop()
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Page Functions (add at the end of app.py)
# ═══════════════════════════════════════════════════════════════════════════════

"""
def show_profile_page():
    '''User Profile Page'''
    st.markdown("### 👤 My Profile")

    user = st.session_state.user
    if not user or user == "guest":
        st.warning("Please login to view profile")
        return

    # Edit profile form
    with st.form("profile_form"):
        st.markdown("#### Personal Information")
        username = st.text_input("Username", value=user.username)
        home_city = st.selectbox("Home City", list(_STARTING_CITIES.keys()),
                                index=list(_STARTING_CITIES.keys()).index(user.home_city))

        st.markdown("#### Skiing Preferences")
        ability = st.select_slider("Skill Level",
                                   options=["Beginner", "Intermediate", "Advanced", "Expert"],
                                   value=user.ski_ability or "Intermediate")

        terrain_options = ["Groomers", "Trees", "Bowls", "Steeps", "Moguls"]
        current_terrain = user.preferred_terrain.split(",") if user.preferred_terrain else []
        terrain = st.multiselect("Preferred Terrain", terrain_options, default=current_terrain)

        if st.form_submit_button("Save Profile", use_container_width=True):
            success, message = AuthManager.update_profile(
                user_id=user.user_id,
                username=username,
                home_city=home_city,
                ski_ability=ability,
                preferred_terrain=",".join(terrain)
            )
            if success:
                st.success(message)
                st.rerun()
            else:
                st.error(message)

    # Ski Passes Management
    st.markdown("### 🎫 My Ski Passes")

    with get_db() as db:
        passes = db.query(UserPass).filter(UserPass.user_id == user.user_id).all()

        if passes:
            for p in passes:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"**{p.pass_type}** {p.pass_tier}")
                with col2:
                    st.write(f"${p.purchase_price:.2f} | {p.days_used}/{p.days_total or '∞'} days")
                with col3:
                    st.caption(f"Expires {p.valid_until}")

        # Add new pass
        with st.expander("➕ Add Ski Pass"):
            with st.form("add_pass_form"):
                pass_type = st.selectbox("Pass Type", ["IKON", "EPIC", "INDY"])
                pass_tier = st.text_input("Tier", placeholder="e.g., Full, Base, 4-Day")
                purchase_price = st.number_input("Purchase Price ($)", min_value=0.0, step=50.0, value=1099.0)

                col1, col2 = st.columns(2)
                with col1:
                    valid_from = st.date_input("Valid From", value=datetime.now().date())
                with col2:
                    valid_until = st.date_input("Valid Until",
                                               value=datetime.now().date() + timedelta(days=180))

                days_total = st.number_input("Total Days (0 = unlimited)", min_value=0, value=0)

                if st.form_submit_button("Add Pass"):
                    new_pass = UserPass(
                        user_id=user.user_id,
                        pass_type=pass_type,
                        pass_tier=pass_tier,
                        purchase_price=purchase_price,
                        valid_from=valid_from,
                        valid_until=valid_until,
                        days_total=days_total if days_total > 0 else None
                    )
                    db.add(new_pass)
                    db.commit()
                    st.success("Pass added!")
                    st.rerun()


def show_trips_page():
    '''My Trips Page'''
    st.markdown("### 🗓️ My Trips")

    user = st.session_state.user
    if not user or user == "guest":
        st.warning("Please login to view trips")
        return

    with get_db() as db:
        trips = db.query(Trip).filter(Trip.user_id == user.user_id).order_by(Trip.start_date.desc()).all()

        if not trips:
            st.info("No trips yet! Use the Trip Planner to create one.")
            return

        for trip in trips:
            with st.expander(f"{trip.trip_name} ({trip.start_date} to {trip.end_date})"):
                days = db.query(TripDay).filter(TripDay.trip_id == trip.trip_id).order_by(TripDay.day_number).all()

                for day in days:
                    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

                    with col1:
                        st.write(f"**Day {day.day_number}:** {day.resort_name}")
                    with col2:
                        st.caption(f"{day.date}")
                    with col3:
                        if day.checked_in:
                            st.success("✓ Visited")
                        else:
                            if st.button("Check In", key=f"checkin_{day.trip_day_id}"):
                                day.checked_in = True
                                day.check_in_time = datetime.utcnow()
                                db.commit()
                                # Update ROI stats
                                ROICalculator.update_season_stats(user.user_id)
                                st.rerun()
                    with col4:
                        if day.rating:
                            st.write("⭐" * day.rating)


def show_stats_page():
    '''Season Statistics & ROI Dashboard'''
    st.markdown("### 📊 Season Statistics")

    user = st.session_state.user
    if not user or user == "guest":
        st.warning("Please login to view stats")
        return

    # Calculate ROI
    roi_data = ROICalculator.calculate_user_roi(user.user_id)

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Days Skied", roi_data['days_skied'])

    with col2:
        st.metric("Resorts Visited", roi_data['unique_resorts'])

    with col3:
        roi_val = roi_data['roi']
        roi_color = "normal" if roi_val >= 0 else "inverse"
        st.metric("Pass ROI", f"${roi_val:,.2f}",
                 delta=f"{roi_data['roi_percentage']:.1f}% return",
                 delta_color=roi_color)

    with col4:
        days_to_break_even = roi_data['break_even_days'] - roi_data['days_skied']
        if days_to_break_even > 0:
            st.metric("To Break Even", f"{days_to_break_even} days")
        else:
            st.metric("Break Even", "✓ Achieved!")

    # Detailed ROI breakdown
    st.markdown("---")
    st.markdown("### 💰 Financial Breakdown")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Pass Cost:** ${roi_data['total_pass_cost']:,.2f}")
        st.markdown(f"**Ticket Value:** ${roi_data['total_ticket_value']:,.2f}")
        if roi_data['days_skied'] > 0:
            avg_value = roi_data['total_ticket_value'] / roi_data['days_skied']
            st.markdown(f"**Avg. Value/Day:** ${avg_value:.2f}")

    with col2:
        if roi_data['best_value_day']:
            date, resort, value = roi_data['best_value_day']
            st.markdown(f"**Best Value Day:**")
            st.markdown(f"  {resort} on {date}")
            st.markdown(f"  Worth ${value:.2f}!")

    # Progress bar
    if roi_data['break_even_days'] > 0:
        progress = min(roi_data['days_skied'] / roi_data['break_even_days'], 1.0)
        st.progress(progress)
        st.caption(f"Progress to break-even: {progress*100:.0f}%")


def show_settings_page():
    '''User Settings Page'''
    st.markdown("### ⚙️ Settings")

    user = st.session_state.user
    if not user or user == "guest":
        st.warning("Please login to view settings")
        return

    # Settings form (to be implemented)
    st.info("Settings page coming soon!")
"""

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Save trips from Trip Planner (modify existing trip planner code)
# ═══════════════════════════════════════════════════════════════════════════════

"""
# In the trip planner button handler, ADD this code after generating the prompt:

if st.session_state.user and st.session_state.user != "guest":
    # Save trip to database
    with get_db() as db:
        trip = Trip(
            user_id=st.session_state.user.user_id,
            trip_name=f"{num_days}-day trip starting {trip_start.strftime('%b %d')}",
            start_date=trip_start,
            end_date=trip_start + timedelta(days=num_days-1),
            total_days=num_days,
            lodging_location=lodging_pref if lodging_pref != "Flexible" else None,
            notes=trip_notes
        )
        db.add(trip)
        db.flush()

        # Create placeholder trip days (resort TBD from agent response)
        for i in range(num_days):
            day = TripDay(
                trip_id=trip.trip_id,
                day_number=i + 1,
                date=trip_start + timedelta(days=i),
                resort_name="TBD"  # Will be updated from agent response
            )
            db.add(day)

        db.commit()
        st.success("Trip saved! View in 'My Trips'")
"""

# ═══════════════════════════════════════════════════════════════════════════════
# END OF INTEGRATION CODE
# ═══════════════════════════════════════════════════════════════════════════════

print("""
To integrate user accounts into app.py:

1. Copy SECTION 1 imports to top of app.py
2. Copy SECTION 2 session state initialization
3. Copy SECTION 3 login/register UI (before main UI code)
4. Copy SECTION 4 sidebar navigation
5. Copy SECTION 5 page functions to end of file
6. Modify trip planner with SECTION 6 code

Then run: python setup_user_accounts.py
""")
