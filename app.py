"""
Colorado Powracle — Streamlit web app.
Run: streamlit run app.py  (from project root, with conda env active)
"""

from concurrent.futures import ThreadPoolExecutor as _TPE
from agent.agent import build_agent
from agent.chat_service import run_chat_turn
from agent.deterministic_answers import try_answer_simple_live_question
from ingestion.snotel_live import fetch_current_snowpack, fetch_all_snowpack
from ingestion.openmeteo_forecast import get_weekend_snowfall
from resorts import RESORT_STATIONS, ALL_PASSES, STARTING_CITIES, resort_passes, pass_filter, haversine_miles
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components
import sys
import os
import math
import re
import ast
from datetime import datetime, timedelta

# User Accounts
from auth.auth_manager import AuthManager
from auth.roi_calculator import ROICalculator
from db.postgres import check_connection, get_db
from models.user import User, UserPass, Trip, TripDay, FavoriteResort, UserSeasonStats

# Ensure project root is on sys.path so package imports work when running via streamlit
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


st.set_page_config(
    page_title="Colorado Powracle",
    page_icon="⛷️",
    layout="wide"
)

st.markdown("""
<style>
/* ── Snowfall effect ──────────────────────────────────────────────── */
/* Hide the markdown container holding the snowfall effect */
div[data-testid="stMarkdownContainer"]:has(#snowfall-container) {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    width: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
    overflow: visible !important;
    z-index: 999999 !important;
}

#snowfall-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    pointer-events: none;
    z-index: 999999;
    overflow: hidden;
}
.snowflake {
    position: fixed;
    top: -10px;
    color: rgba(255, 255, 255, 0.85);
    text-shadow: 0 0 3px rgba(255, 255, 255, 0.5);
    font-size: 1em;
    pointer-events: none;
    animation: fall linear infinite;
    user-select: none;
}
@keyframes fall {
    0% {
        transform: translateY(-10px) rotate(0deg);
    }
    100% {
        transform: translateY(100vh) rotate(360deg);
    }
}

/* ── Unified text hierarchy ───────────────────────────────────────── */
/* L3 — Content text: widget labels, dropdowns, radio, captions, chat */
[data-testid="stWidgetLabel"] p,
label,
[data-testid="stSelectbox"] div[data-baseweb="select"] span,
[data-testid="stMultiSelect"] span,
.stRadio label span,
[data-testid="stCaptionContainer"] p,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatInput"] textarea {
    font-size: 0.97rem !important;
    line-height: 1.6 !important;
}

/* ── Expanders (map & trip planner) ──────────────────────────────── */
[data-testid="stExpander"] {
    border: 1.5px solid rgba(99, 179, 237, 0.2) !important;
    border-radius: 16px !important;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2) !important;
    overflow: hidden !important;
}
/* Trip planner specific styling */
[data-testid="stExpander"]:has(button[aria-label*="Trip"]) {
    background: linear-gradient(135deg, rgba(52,211,153,0.03), rgba(41,182,246,0.03));
    border-color: rgba(52,211,153,0.25) !important;
}

/* ── Plotly chart rounding ────────────────────────────────────────── */
[data-testid="stPlotlyChart"] {
    border-radius: 14px !important;
    overflow: hidden !important;
}
[data-testid="stPlotlyChart"] > div,
[data-testid="stPlotlyChart"] iframe {
    border-radius: 14px !important;
    overflow: hidden !important;
}

/* ── Chat messages ────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    border-radius: 14px !important;
    border-width: 1px !important;
    border-style: solid !important;
    border-color: rgba(99, 179, 237, 0.12) !important;
}

/* ── Resort cards ─────────────────────────────────────────────────── */
.resort-card {
    padding: 9px 13px;
    margin-bottom: 5px;
    border-radius: 11px;
    border: 1px solid rgba(99, 179, 237, 0.1);
    background: rgba(255, 255, 255, 0.04);
    transition: border-color 0.18s, background 0.18s;
    line-height: 1.5;
}
.resort-card:hover {
    border-color: rgba(99, 179, 237, 0.28);
    background: rgba(255, 255, 255, 0.07);
}
.resort-card-top {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
}
.resort-dot { font-size: 1.1em; vertical-align: middle; line-height: 1; }
.resort-name { font-weight: 600; font-size: 0.97rem; }
.resort-dist { font-size: 0.88rem; opacity: 0.55; margin-left: auto; white-space: nowrap; }
.resort-stats { font-size: 0.97rem; opacity: 0.72; margin-top: 1px; padding-left: 20px; }
.resort-no-data { font-size: 0.88rem; opacity: 0.5; margin-top: 1px; padding-left: 20px; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# User Account Pages - Defined early to avoid st.rerun() issues
# ══════════════════════════════════════════════════════════════════════════════

def show_profile_page():
    """Profile page - edit user info and manage ski passes"""
    st.title("👤 My Profile")

    user = st.session_state.user

    # ── Profile Info ──────────────────────────────────────────────────────────
    st.markdown("### Profile Information")

    with st.form("profile_form"):
        username = st.text_input("Username", value=user.username)
        home_city = st.text_input("Home City", value=user.home_city or "Denver")
        ski_ability = st.selectbox(
            "Ski Ability",
            ["Beginner", "Intermediate", "Advanced", "Expert"],
            index=["Beginner", "Intermediate", "Advanced", "Expert"].index(user.ski_ability or "Intermediate")
        )
        preferred_terrain = st.multiselect(
            "Preferred Terrain",
            ["Groomers", "Trees", "Bowls", "Moguls", "Park"],
            default=user.preferred_terrain.split(",") if user.preferred_terrain else []
        )

        if st.form_submit_button("Update Profile", use_container_width=True):
            success, message = AuthManager.update_profile(
                user.user_id,
                username=username,
                home_city=home_city,
                ski_ability=ski_ability,
                preferred_terrain=",".join(preferred_terrain)
            )
            if success:
                st.success(message)
                # Update session state
                try:
                    with get_db() as db:
                        updated_user = db.query(User).filter(User.user_id == user.user_id).first()
                        # Access attributes and expunge to make independent of session
                        _ = updated_user.user_id, updated_user.username, updated_user.email, updated_user.home_city, updated_user.ski_ability, updated_user.preferred_terrain
                        db.expunge(updated_user)
                        st.session_state.user = updated_user
                except Exception as e:
                    st.warning(f"Profile saved but session could not be refreshed — please reload the page. ({e})")
                st.rerun()
            else:
                st.error(message)

    st.divider()

    # ── Ski Passes ────────────────────────────────────────────────────────────
    st.markdown("### My Ski Passes")

    # Display existing passes - convert to dict to avoid detached instance errors
    try:
        with get_db() as db:
            passes_query = db.query(UserPass).filter(UserPass.user_id == user.user_id).all()
            # Convert to dicts to detach from session
            passes = [{
                'user_pass_id': p.user_pass_id,
                'pass_type': p.pass_type,
                'pass_tier': p.pass_tier,
                'purchase_price': p.purchase_price,
                'day_ticket_price': p.day_ticket_price,
                'valid_from': p.valid_from,
                'valid_until': p.valid_until,
                'days_used': p.days_used
            } for p in passes_query]
    except Exception as e:
        st.error(f"Could not load ski passes — database unavailable. ({e})")
        passes = []

    if passes:
        for pass_obj in passes:
            with st.expander(f"{pass_obj['pass_type']} - {pass_obj['pass_tier']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Purchase Price:** ${pass_obj['purchase_price']:.2f}")
                    if pass_obj['day_ticket_price']:
                        st.write(f"**Day Ticket Price:** ${pass_obj['day_ticket_price']:.2f}")
                    st.write(f"**Valid From:** {pass_obj['valid_from']}")
                with col2:
                    st.write(f"**Valid Until:** {pass_obj['valid_until']}")
                    st.write(f"**Days Used:** {pass_obj['days_used']}")

                if st.button(f"Delete", key=f"delete_pass_{pass_obj['user_pass_id']}"):
                    try:
                        with get_db() as db:
                            db.query(UserPass).filter(UserPass.user_pass_id == pass_obj['user_pass_id']).delete()
                            db.commit()
                        st.success("Pass deleted")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not delete pass — database unavailable. ({e})")
    else:
        st.info("No ski passes added yet")

    # Add new pass
    st.markdown("#### Add New Pass")
    with st.form("add_pass_form"):
        pass_type = st.selectbox("Pass Type", ["Ikon", "Epic", "Indy", "Powder Alliance"])
        pass_tier = st.selectbox("Pass Tier", ["Base", "Full", "Plus"])

        col1, col2 = st.columns(2)
        with col1:
            purchase_price = st.number_input("Purchase Price ($)", min_value=0.0, value=699.0,
                                             help="What you paid for the pass")
        with col2:
            day_ticket_price = st.number_input("Avg Day Ticket Price ($)", min_value=0.0, value=150.0,
                                               help="Average cost of a day ticket at resorts you'll visit")

        col3, col4 = st.columns(2)
        with col3:
            valid_from = st.date_input("Valid From", value=datetime(2024, 11, 1).date())
        with col4:
            valid_until = st.date_input("Valid Until", value=datetime(2025, 4, 30).date())

        if st.form_submit_button("Add Pass", use_container_width=True):
            new_pass = UserPass(
                user_id=user.user_id,
                pass_type=pass_type,
                pass_tier=pass_tier,
                purchase_price=purchase_price,
                day_ticket_price=day_ticket_price if day_ticket_price > 0 else None,
                valid_from=valid_from,
                valid_until=valid_until,
                days_used=0
            )
            try:
                with get_db() as db:
                    db.add(new_pass)
                    db.commit()
                st.success(f"{pass_type} {pass_tier} pass added!")
                st.rerun()
            except Exception as e:
                st.error(f"Could not save pass — database unavailable. ({e})")

    st.divider()

    # ── Quick Add Ski Days ────────────────────────────────────────────────────
    st.markdown("### ⛷️ Log Ski Days")
    st.caption("Quickly log past ski days to track your pass ROI")

    # Get all user's passes OUTSIDE the form to avoid detached instance errors
    try:
        with get_db() as db:
            all_passes_query = db.query(UserPass).filter(UserPass.user_id == user.user_id).all()
            all_passes = [{
                'user_pass_id': p.user_pass_id,
                'pass_type': p.pass_type,
                'pass_tier': p.pass_tier,
                'valid_from': p.valid_from,
                'valid_until': p.valid_until
            } for p in all_passes_query]
    except Exception as e:
        st.error(f"Could not load passes for ski day logging — database unavailable. ({e})")
        all_passes = []

    with st.form("add_ski_day_form"):
        col1, col2 = st.columns(2)
        with col1:
            ski_date = st.date_input("Date Skied", value=datetime.now().date(), max_value=datetime.now().date())
        with col2:
            # Get list of resorts from RESORT_STATIONS
            resort_list = sorted(RESORT_STATIONS.keys())
            resort_skied = st.selectbox("Resort", resort_list)

        # Pass vs Day Ticket selection
        ticket_type = st.radio(
            "Ticket Type",
            ["Used Season Pass", "Bought Day Ticket"],
            help="Select whether you used a season pass or purchased a day ticket"
        )

        pass_id_used = None
        ticket_cost = None

        if ticket_type == "Used Season Pass":
            if all_passes:
                pass_options = {f"{p['pass_type']} {p['pass_tier']}": p['user_pass_id'] for p in all_passes}
                selected_pass = st.selectbox("Which Pass?", list(pass_options.keys()))
                pass_id_used = pass_options[selected_pass]
            else:
                st.warning("No passes found. Add a pass above or select 'Bought Day Ticket'.")
        else:
            ticket_cost = st.number_input("Day Ticket Cost ($)", min_value=0.0, value=150.0, step=10.0)

        notes = st.text_area("Notes (optional)", placeholder="e.g., 'Great powder day!', 'Skied the back bowls'")

        if st.form_submit_button("Log Ski Day", use_container_width=True):
            # Validate pass is valid for the date if using a pass
            if ticket_type == "Used Season Pass" and pass_id_used:
                selected_pass_info = next((p for p in all_passes if p['user_pass_id'] == pass_id_used), None)
                if selected_pass_info:
                    if not (selected_pass_info['valid_from'] <= ski_date <= selected_pass_info['valid_until']):
                        st.error(f"The selected pass is not valid on {ski_date.strftime('%b %d, %Y')}. "
                                f"Pass is valid from {selected_pass_info['valid_from']} to {selected_pass_info['valid_until']}.")
                        st.stop()

            # Create a single-day trip for this ski day
            try:
                new_trip = Trip(
                    user_id=user.user_id,
                    trip_name=f"{resort_skied} - {ski_date.strftime('%b %d')}",
                    start_date=ski_date,
                    end_date=ski_date,
                    total_days=1,
                    notes=notes if notes.strip() else None
                )

                with get_db() as db:
                    db.add(new_trip)
                    db.commit()
                    db.refresh(new_trip)

                    # Create trip day already checked in
                    trip_day = TripDay(
                        trip_id=new_trip.trip_id,
                        day_number=1,
                        date=ski_date,
                        resort_name=resort_skied,
                        checked_in=True,
                        check_in_time=datetime.now(),
                        used_pass=(ticket_type == "Used Season Pass"),
                        pass_used_id=pass_id_used,
                        day_ticket_cost=ticket_cost if ticket_type == "Bought Day Ticket" else None
                    )
                    db.add(trip_day)
                    db.commit()

                    # Update pass days_used only if they used a pass
                    if ticket_type == "Used Season Pass" and pass_id_used:
                        pass_obj = db.query(UserPass).filter(UserPass.user_pass_id == pass_id_used).first()
                        if pass_obj:
                            pass_obj.days_used += 1
                            db.commit()

                st.success(f"Logged ski day at {resort_skied}! Check Season Stats to see your ROI.")
                st.rerun()
            except Exception as e:
                st.error(f"Error logging ski day: {e}")


def show_trips_page():
    """Trips page - view trip history and check in to ski days"""
    st.title("🎿 My Trips")

    user = st.session_state.user

    # Get all trips for user - convert to dicts to avoid detached instance errors
    try:
        with get_db() as db:
            trips_query = db.query(Trip).filter(Trip.user_id == user.user_id).order_by(Trip.start_date.desc()).all()
            trips = [{
                'trip_id': t.trip_id,
                'start_date': t.start_date,
                'end_date': t.end_date,
                'total_days': t.total_days,
                'lodging_location': t.lodging_location
            } for t in trips_query]
    except Exception as e:
        st.error(f"Could not load trips — database unavailable. ({e})")
        return

    if not trips:
        st.info("No trips yet. Create a trip using the Smart Trip Planner on the Home page!")
        return

    # Display trips
    for trip in trips:
        with st.expander(f"📅 {trip['start_date']} → {trip['end_date']} ({trip['total_days']} days)", expanded=True):
            st.markdown(f"**Lodging:** {trip['lodging_location'] or 'Not specified'}")

            # Get trip days - convert to dicts
            try:
                with get_db() as db:
                    trip_days_query = db.query(TripDay).filter(TripDay.trip_id == trip['trip_id']).order_by(TripDay.date).all()
                    trip_days = [{
                        'trip_day_id': d.trip_day_id,
                        'date': d.date,
                        'resort_name': d.resort_name,
                        'checked_in': d.checked_in,
                        'rating': d.rating,
                        'review': d.review
                    } for d in trip_days_query]
            except Exception as e:
                st.error(f"Could not load trip days — database unavailable. ({e})")
                trip_days = []

            if trip_days:
                st.markdown("#### Ski Days")
                for day in trip_days:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    with col1:
                        st.write(f"**{day['date']}** - {day['resort_name']}")
                    with col2:
                        if day['checked_in']:
                            st.success("✓ Checked In")
                        else:
                            if st.button("Check In", key=f"checkin_{day['trip_day_id']}"):
                                # Check in to this day
                                try:
                                    with get_db() as db:
                                        day_obj = db.query(TripDay).filter(TripDay.trip_day_id == day['trip_day_id']).first()
                                        day_obj.checked_in = True
                                        day_obj.check_in_time = datetime.now()
                                        db.commit()

                                        # Update pass days_used
                                        pass_obj = db.query(UserPass).filter(
                                            UserPass.user_id == user.user_id,
                                            UserPass.valid_from <= day['date'],
                                            UserPass.valid_until >= day['date']
                                        ).first()
                                        if pass_obj:
                                            pass_obj.days_used += 1
                                            db.commit()

                                    st.success("Checked in!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Could not check in — database unavailable. ({e})")
                    with col3:
                        if day['checked_in'] and day['rating']:
                            st.write(f"⭐ {day['rating']}/5")

                    # Show review if exists
                    if day['checked_in'] and day['review']:
                        st.caption(f"💬 {day['review']}")

            # Add rating/review form for checked-in days
            checked_in_days = [d for d in trip_days if d['checked_in'] and not d['rating']]
            if checked_in_days:
                st.markdown("#### Rate Your Experience")
                for day in checked_in_days:
                    with st.form(f"rate_day_{day['trip_day_id']}"):
                        st.write(f"**{day['date']} - {day['resort_name']}**")
                        rating = st.slider("Rating", 1, 5, 3)
                        review = st.text_area("Review (optional)")

                        if st.form_submit_button("Submit Rating"):
                            try:
                                with get_db() as db:
                                    day_obj = db.query(TripDay).filter(TripDay.trip_day_id == day['trip_day_id']).first()
                                    day_obj.rating = rating
                                    day_obj.review = review
                                    db.commit()
                                st.success("Rating submitted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not save rating — database unavailable. ({e})")


def show_stats_page():
    """Season stats page - ROI dashboard"""
    st.title("📊 Season Statistics")

    user = st.session_state.user

    # Get current season
    now = datetime.now()
    season = f"{now.year - 1}-{now.year}" if now.month < 7 else f"{now.year}-{now.year + 1}"

    # Calculate ROI
    roi_data = ROICalculator.calculate_user_roi(user.user_id, season)

    # Debug info
    with st.expander("🔍 Debug Info", expanded=False):
        st.write(f"**Season:** {season}")
        st.write(f"**User ID:** {user.user_id}")
        st.write(f"**ROI Data:**")
        st.json({k: str(v) for k, v in roi_data.items()})

    if not roi_data or roi_data['days_skied'] == 0:
        if roi_data and roi_data['total_pass_cost'] > 0:
            st.warning("You have a pass but no ski days logged yet. Go to Profile → Log Ski Days to start tracking!")
        else:
            st.info("No ski pass data available. Add a ski pass in your Profile to see ROI stats!")
        # Still show the empty state with zero values
        if not roi_data:
            return

    # Display ROI metrics
    st.markdown(f"### Season {season}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Days Skied", roi_data["days_skied"])
    with col2:
        st.metric("Pass Cost", f"${float(roi_data['total_pass_cost']):.2f}")
    with col3:
        st.metric("Ticket Value", f"${float(roi_data['total_ticket_value']):.2f}")
    with col4:
        roi_color = "normal" if roi_data["roi"] >= 0 else "inverse"
        st.metric("ROI", f"${float(roi_data['roi']):.2f}", delta=f"{float(roi_data['roi_percentage']):.1f}%")

    # Day ticket purchases
    if roi_data.get("day_ticket_days", 0) > 0:
        st.divider()
        st.markdown("### 🎫 Day Ticket Purchases")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Days with Day Tickets", roi_data["day_ticket_days"])
        with col2:
            st.metric("Total Day Ticket Cost", f"${float(roi_data['total_day_ticket_cost']):.2f}")
        st.caption("These days didn't use your pass and count as additional costs")

    # Break-even progress
    st.divider()
    st.markdown("### Break-Even Progress")
    days_to_break_even = roi_data.get("break_even_days", 0)
    progress = min(roi_data["days_skied"] / days_to_break_even, 1.0) if days_to_break_even > 0 else 0
    st.progress(progress)
    st.caption(f"Need {days_to_break_even} days to break even. {max(0, days_to_break_even - roi_data['days_skied'])} days to go!")

    # Best value days
    if roi_data.get("best_value_days") and len(roi_data["best_value_days"]) > 0:
        st.markdown("### Top Value Days")
        st.caption("Days where you saved the most vs buying a day ticket")

        for i, day in enumerate(roi_data["best_value_days"][:5], 1):
            st.write(f"{i}. **{day['date']}** - {day['resort']} (${float(day['value_saved']):.2f} saved)")

    # Trip history summary
    try:
        with get_db() as db:
            total_trips = db.query(Trip).filter(Trip.user_id == user.user_id).count()
            avg_rating = db.query(TripDay).filter(
                TripDay.trip_id.in_(db.query(Trip.trip_id).filter(Trip.user_id == user.user_id)),
                TripDay.rating.isnot(None)
            ).with_entities(TripDay.rating).all()
    except Exception as e:
        st.error(f"Could not load trip summary — database unavailable. ({e})")
        total_trips, avg_rating = 0, []

    st.divider()
    st.markdown("### Trip Summary")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Trips", total_trips)
    with col2:
        if avg_rating:
            avg = sum(r[0] for r in avg_rating) / len(avg_rating)
            st.metric("Average Rating", f"{avg:.1f}/5 ⭐")
        else:
            st.metric("Average Rating", "N/A")


def show_settings_page():
    """Settings page - account settings"""
    st.title("⚙️ Settings")

    user = st.session_state.user

    # Email preferences
    st.markdown("### Notifications")
    st.info("Email notification settings coming soon!")

    # Data export
    st.markdown("### Data Export")
    if st.button("Export My Data", use_container_width=True):
        st.info("Data export feature coming soon!")

    # Danger zone
    st.divider()
    st.markdown("### Danger Zone")
    with st.expander("Delete Account", expanded=False):
        st.warning("This action cannot be undone. All your trips, ratings, and data will be permanently deleted.")

        confirm = st.text_input("Type 'DELETE' to confirm")
        if st.button("Delete My Account", type="primary"):
            if confirm == "DELETE":
                try:
                    with get_db() as db:
                        db.query(User).filter(User.user_id == user.user_id).delete()
                        db.commit()
                    st.session_state.user = None
                    st.success("Account deleted")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not delete account — database unavailable. ({e})")
            else:
                st.error("Please type 'DELETE' to confirm")


# ── Agent + chat history (once per session) ───────────────────────────────────

if "agent" not in st.session_state:
    st.session_state.agent = build_agent(verbose=True)
    st.session_state.messages = []

# User Accounts session state
if "user" not in st.session_state:
    st.session_state.user = None

if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# ── User Authentication (check early to prevent unnecessary rendering) ─────────

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
                    st.rerun()
                else:
                    st.error(message)

    with tab2:
        with st.form("register_form"):
            reg_email = st.text_input("Email", key="reg_email")
            reg_username = st.text_input("Username", key="reg_username")
            reg_password = st.text_input("Password", type="password", key="reg_password",
                                        help="Minimum 8 characters")

            # Use a list of cities for registration
            _CITIES_LIST = ["Denver", "Boulder", "Colorado Springs", "Fort Collins", "Pueblo", "Grand Junction"]
            reg_home = st.selectbox("Home City", _CITIES_LIST, key="reg_home")

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

# ── Cache functions (defined here, called after page skeleton renders) ─────────


@st.cache_data(ttl=1800)
def load_conditions():
    """Single batch SNOTEL call for all stations — ~10x faster than per-resort calls."""
    # Multiple resorts can share a station; map triplet → list of resorts
    station_to_resorts: dict[str, list[str]] = {}
    for resort, info in RESORT_STATIONS.items():
        sid = info.get("station_id")
        if sid:
            station_to_resorts.setdefault(sid, []).append(resort)

    batch = fetch_all_snowpack(list(station_to_resorts.keys()))
    out = {resort: None for resort in RESORT_STATIONS}
    for triplet, data in batch.items():
        for resort in station_to_resorts.get(triplet, []):
            out[resort] = data
    return out


@st.cache_data(ttl=10800)
def load_forecasts():
    """Weekend snowfall forecast for all resorts — parallel Open-Meteo calls."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch(resort, info):
        if not info.get("lat"):
            return resort, None
        try:
            return resort, get_weekend_snowfall(info["lat"], info["lon"])
        except Exception:
            return resort, None

    out = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch, r, i): r for r,
                   i in RESORT_STATIONS.items()}
        for f in as_completed(futures):
            resort, data = f.result()
            out[resort] = data
    return out


@st.cache_data(ttl=10800)
def load_7day_forecasts():
    """Full 7-day forecast for all resorts — parallel Open-Meteo calls."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ingestion.openmeteo_forecast import fetch_snow_forecast

    def _fetch(resort, info):
        if not info.get("lat"):
            return resort, None
        try:
            return resort, fetch_snow_forecast(info["lat"], info["lon"], days=7)
        except Exception:
            return resort, None

    out = {}
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(_fetch, r, i): r for r,
                   i in RESORT_STATIONS.items()}
        for f in as_completed(futures):
            resort, data = f.result()
            out[resort] = data
    return out


# ── Filter helpers ────────────────────────────────────────────────────────────


def _apply_quick_filters(
    visible: dict, forecasts: dict,
    user_lat: float, user_lon: float,
) -> dict:
    """Apply the 4 quick-filter checkboxes to a visible-resort dict."""
    if st.session_state.get("filter_powder", False):
        visible = {r: d for r, d in visible.items() if d and d.get("new_snow_72h", 0) >= 6}
    if st.session_state.get("filter_base", False):
        visible = {r: d for r, d in visible.items() if d and d.get("snow_depth_in", 0) >= 50}
    if st.session_state.get("filter_distance", False):
        visible = {r: d for r, d in visible.items()
                   if haversine_miles(user_lat, user_lon,
                                       RESORT_STATIONS[r]["lat"],
                                       RESORT_STATIONS[r]["lon"]) < 100}
    if st.session_state.get("filter_forecast", False) and forecasts:
        visible = {r: d for r, d in visible.items()
                   if forecasts.get(r) and forecasts[r].get("weekend_total_in", 0) >= 4}
    return visible


# Map marker style per pass
_PASS_STYLE = {
    "IKON": {"symbol": "circle", "border": "#29B6F6"},
    "EPIC": {"symbol": "circle", "border": "#CE93D8"},
    "INDY": {"symbol": "circle", "border": "#66BB6A"},
}

# Colored HTML pill per pass (used in condition cards)
_PASS_BADGE = {
    "IKON": '<span style="background:rgba(41,182,246,0.18);color:#7dd3fc;padding:2px 7px;border-radius:20px;font-size:0.7em;font-weight:700;letter-spacing:0.07em;border:1px solid rgba(41,182,246,0.3)">IKON</span>',
    "EPIC": '<span style="background:rgba(167,139,250,0.18);color:#c4b5fd;padding:2px 7px;border-radius:20px;font-size:0.7em;font-weight:700;letter-spacing:0.07em;border:1px solid rgba(167,139,250,0.3)">EPIC</span>',
    "INDY": '<span style="background:rgba(52,211,153,0.18);color:#6ee7b7;padding:2px 7px;border-radius:20px;font-size:0.7em;font-weight:700;letter-spacing:0.07em;border:1px solid rgba(52,211,153,0.3)">INDY</span>',
}


def _blues_color(t: float) -> str:
    """Map t ∈ [0, 1] to a soft blue hex color visible on a light background."""
    stops = [
        (0.000, (200, 225, 248)),
        (0.125, (160, 203, 238)),
        (0.250, (110, 174, 222)),
        (0.375, (70, 144, 205)),
        (0.500, (40, 112, 185)),
        (0.625, (20,  82, 158)),
        (0.750, (10,  57, 130)),
        (0.875, (5,  37,  99)),
        (1.000, (2,  20,  70)),
    ]
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return f"#{r:02x}{g:02x}{b:02x}"
    return "#021446"


# Matching colorscale for Plotly map markers (same stops as _blues_color)
_SNOW_CS = [
    [0.000, "rgb(200,225,248)"],
    [0.125, "rgb(160,203,238)"],
    [0.250, "rgb(110,174,222)"],
    [0.375, "rgb(70,144,205)"],
    [0.500, "rgb(40,112,185)"],
    [0.625, "rgb(20,82,158)"],
    [0.750, "rgb(10,57,130)"],
    [0.875, "rgb(5,37,99)"],
    [1.000, "rgb(2,20,70)"],
]


# ── Seed session state so widgets work on first load ──────────────────────────

if "pass_filter" not in st.session_state:
    st.session_state.pass_filter = ["All"]
if "start_city" not in st.session_state:
    st.session_state.start_city = "Denver"
if "sort_by" not in st.session_state:
    st.session_state.sort_by = "🌨️ Fresh Snow"
if "quick_filters" not in st.session_state:
    st.session_state.quick_filters = []
if "snowfall_enabled" not in st.session_state:
    st.session_state.snowfall_enabled = False
if "use_deterministic_simple_answers" not in st.session_state:
    st.session_state.use_deterministic_simple_answers = False

# ── First-load detection ───────────────────────────────────────────────────────
# On first load, conditions are not yet fetched. We render the layout (including
# the chat column) immediately so the user can start typing, then load data in
# the background and fill the cards placeholder before calling st.rerun() to
# show the map. On every subsequent rerun, data comes instantly from session state.

_first_load = "conditions" not in st.session_state

# ── Widget values from session state (used by map, which renders before widgets) ─

selected_passes = st.session_state.pass_filter or ["All"]
city_name       = st.session_state.start_city
sort_by         = st.session_state.sort_by
user_lat, user_lon = STARTING_CITIES[city_name]

# ── Pre-compute display values (only when data is available) ──────────────────

if not _first_load:
    conditions    = st.session_state.conditions
    forecasts     = st.session_state.forecasts
    visible       = {r: d for r, d in conditions.items() if pass_filter(r, selected_passes)}
    visible       = _apply_quick_filters(visible, forecasts, user_lat, user_lon)
    vis_names     = list(visible.keys())
    _use_base_map = sort_by == "🏔️ Base Snow"
    _map_field    = "snow_depth_in" if _use_base_map else "new_snow_72h"
    _map_label    = "Base depth (in)" if _use_base_map else "72h snow (in)"
    _map_floor    = 30 if _use_base_map else 6
    _map_scale    = 0.2 if _use_base_map else 2
    _all_map_vals = [visible[r].get(_map_field, 0) if visible[r] else 0 for r in vis_names]
    _CMIN         = 0
    _CMAX         = max(max(_all_map_vals, default=0), _map_floor)

# ── Map (full-width, inline — only once data is loaded) ───────────────────────

# Show map on Home page or for guest users (who are always on home)
if not _first_load and (st.session_state.current_page == "Home" or st.session_state.user == "guest"):
    with st.expander("🗺️ Show Resort Map", expanded=False):
            fig = go.Figure()

            # Precompute per-pass data once, reused across both render loops
            _pass_data = {}
            for pass_name, style in _PASS_STYLE.items():
                p_resorts = [r for r in vis_names
                             if pass_name in RESORT_STATIONS[r].get("pass", [])]
                if not p_resorts:
                    continue
                p_snows = [visible[r].get("new_snow_72h", 0)
                           if visible[r] else 0 for r in p_resorts]
                p_bases = [visible[r].get("snow_depth_in", 0)
                           if visible[r] else 0 for r in p_resorts]
                p_map_vals = [p_bases[i] if _use_base_map else p_snows[i]
                              for i in range(len(p_resorts))]
                p_dists = [haversine_miles(user_lat, user_lon,
                                            RESORT_STATIONS[r]["lat"], RESORT_STATIONS[r]["lon"])
                           for r in p_resorts]
                p_texts = [
                    (f"<b>{r}</b>  [{pass_name}]<br>"
                     f"❄ New 72h: {p_snows[i]:.0f}\"  ·  Base: {p_bases[i]:.0f}\"<br>"
                     f"📍 {p_dists[i]:.0f} mi from {city_name}")
                    for i, r in enumerate(p_resorts)
                ]
                p_sizes = [max(10, min(36, v * _map_scale + 10))
                           for v in p_map_vals]
                _pass_data[pass_name] = dict(
                    resorts=p_resorts, map_vals=p_map_vals,
                    texts=p_texts, sizes=p_sizes, style=style,
                )

            # Layer 1 — pass-colored halos (rendered first, sit underneath)
            for pass_name, d in _pass_data.items():
                fig.add_trace(go.Scattermap(
                    lat=[RESORT_STATIONS[r]["lat"] for r in d["resorts"]],
                    lon=[RESORT_STATIONS[r]["lon"] for r in d["resorts"]],
                    mode="markers",
                    name=pass_name,
                    hoverinfo="skip",
                    marker=dict(
                        size=[min(s + 12, 48) for s in d["sizes"]],
                        color=d["style"]["border"],
                        opacity=0.55,
                    ),
                ))

            # Layer 2 — snow-level colorscale fill (rendered on top, carries hover + colorbar)
            first_colorbar = True
            for pass_name, d in _pass_data.items():
                colorbar_cfg = dict(
                    title=dict(text=_map_label, font=dict(
                        color="#0d1b2e", size=11)),
                    thickness=12, len=0.55,
                    tickfont=dict(color="#0d1b2e", size=10),
                    bgcolor="rgba(220,238,255,0.92)",
                    bordercolor="#90b8d8",
                    borderwidth=1,
                ) if first_colorbar else None
                fig.add_trace(go.Scattermap(
                    lat=[RESORT_STATIONS[r]["lat"] for r in d["resorts"]],
                    lon=[RESORT_STATIONS[r]["lon"] for r in d["resorts"]],
                    text=d["texts"],
                    hoverinfo="text",
                    mode="markers",
                    showlegend=False,
                    marker=dict(
                        size=d["sizes"],
                        color=d["map_vals"],
                        colorscale=_SNOW_CS,
                        cmin=_CMIN, cmax=_CMAX,
                        showscale=first_colorbar,
                        colorbar=colorbar_cfg,
                        opacity=0.95,
                    ),
                ))
                first_colorbar = False

            fig.add_trace(go.Scattermap(
                lat=[user_lat], lon=[user_lon],
                mode="markers+text",
                text=[f"  {city_name}"],
                textposition="bottom right",
                textfont=dict(color="#b83200", size=12, family="Arial Black"),
                hovertext=f"📍 {city_name}",
                hoverinfo="text",
                marker=dict(size=18, color="#e03c00"),
                name="📍 You",
                showlegend=True,
            ))

            fig.update_layout(
                map=dict(
                    style="white-bg",
                    layers=[{
                        "below": "traces",
                        "sourcetype": "raster",
                        "source": ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}"],
                        "sourceattribution": "© Esri / World Topo Map",
                    }],
                    center=dict(lat=39.0, lon=-105.55),
                    zoom=6.5,
                ),
                margin={"r": 0, "t": 0, "l": 0, "b": 0},
                height=520,
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    x=0.01, y=0.99,
                    bgcolor="rgba(220,238,255,0.92)",
                    bordercolor="#90b8d8",
                    borderwidth=1,
                    font=dict(color="#0d1b2e", size=11),
                    itemsizing="constant",
                ),
            )
            st.plotly_chart(fig, width="stretch")

# ── Sidebar Navigation (for logged-in users) ─────────────────────────────────

if db_available and st.session_state.user and isinstance(st.session_state.user, User):
    with st.sidebar:
        st.markdown(f"### 👤 {st.session_state.user.username}")
        st.caption(f"📍 {st.session_state.user.home_city}")
        st.divider()

        # Page navigation
        page = st.radio(
            "Navigate",
            ["Home", "Profile", "My Trips", "Season Stats", "Settings"],
            index=["Home", "Profile", "My Trips", "Season Stats", "Settings"].index(st.session_state.current_page),
            key="page_nav"
        )

        # Update current page
        if page != st.session_state.current_page:
            st.session_state.current_page = page
            st.rerun()

        st.divider()

        # Logout button
        if st.button("Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.current_page = "Home"
            st.rerun()

# ── Route to different pages ─────────────────────────────────────────────────

if db_available and st.session_state.user and isinstance(st.session_state.user, User) and st.session_state.current_page != "Home":
    # Show different page based on selection
    if st.session_state.current_page == "Profile":
        show_profile_page()
    elif st.session_state.current_page == "My Trips":
        show_trips_page()
    elif st.session_state.current_page == "Season Stats":
        show_stats_page()
    elif st.session_state.current_page == "Settings":
        show_settings_page()
    st.stop()  # Don't render home page content

# ── Two-column layout: conditions | chat ─────────────────────────────────────

col_left, col_right = st.columns([1, 1.5], gap="large")

# ── LEFT: controls + live condition cards ────────────────────────────────────

with col_left:
    # Title with snowfall toggle (isolated fragment to prevent full page rerun)
    @st.fragment
    def snowfall_toggle():
        title_col, toggle_col = st.columns([4, 1])
        with title_col:
            st.markdown("### ⛷️ Colorado Powracle")
        with toggle_col:
            st.checkbox(
                "❄️",
                value=st.session_state.snowfall_enabled,
                key="snowfall_enabled",
                help="Toggle snowfall effect"
            )

        # Render snowfall effect inside fragment so it updates on toggle
        if st.session_state.snowfall_enabled:
            import random
            random.seed(42)  # Consistent positions across reruns

            snowflakes_html = '<div id="snowfall-container">'
            for i in range(50):
                left = random.randint(0, 100)
                size = random.uniform(0.5, 1.5)
                opacity = random.uniform(0.3, 0.9)
                duration = random.uniform(10, 25)
                delay = random.uniform(0, 10)

                snowflakes_html += f'<div class="snowflake" style="left:{left}%;font-size:{size}em;opacity:{opacity};animation-duration:{duration}s;animation-delay:{delay}s;">❄</div>'
            snowflakes_html += '</div>'

            st.markdown(snowflakes_html, unsafe_allow_html=True)

    snowfall_toggle()

    # ── Today's Leaders banner ────────────────────────────────────────────
    if not _first_load:
        # Find today's leaders
        valid_resorts = {r: d for r, d in conditions.items() if d is not None}

        # Most fresh snow (72h)
        if valid_resorts:
            top_fresh = max(valid_resorts.items(), key=lambda x: x[1].get("new_snow_72h", 0))
            top_fresh_name = top_fresh[0]
            top_fresh_val = top_fresh[1].get("new_snow_72h", 0)

            # Best base
            top_base = max(valid_resorts.items(), key=lambda x: x[1].get("snow_depth_in", 0))
            top_base_name = top_base[0]
            top_base_val = top_base[1].get("snow_depth_in", 0)

            # Closest powder (6"+ new snow, sorted by distance)
            powder_resorts = [(r, d) for r, d in valid_resorts.items() if d.get("new_snow_72h", 0) >= 6]
            if powder_resorts:
                closest_powder = min(powder_resorts, key=lambda x: haversine_miles(
                    user_lat, user_lon,
                    RESORT_STATIONS[x[0]]["lat"],
                    RESORT_STATIONS[x[0]]["lon"]
                ))
                closest_powder_name = closest_powder[0]
                closest_powder_dist = haversine_miles(
                    user_lat, user_lon,
                    RESORT_STATIONS[closest_powder_name]["lat"],
                    RESORT_STATIONS[closest_powder_name]["lon"]
                )
                closest_powder_snow = closest_powder[1].get("new_snow_72h", 0)
                closest_powder_text = f"{closest_powder_name} ({closest_powder_snow:.0f}\" · {closest_powder_dist:.0f}mi)"
            else:
                closest_powder_text = "None (6\"+ needed)"

            st.markdown(f'''
            <div style="background:linear-gradient(135deg, rgba(41,182,246,0.08), rgba(167,139,250,0.08));
                        border:1px solid rgba(99,179,237,0.2);
                        border-radius:10px;
                        padding:10px 12px;
                        margin-bottom:12px;">
                <div style="font-size:0.78rem;font-weight:600;opacity:0.6;margin-bottom:6px;letter-spacing:0.05em;">TODAY'S LEADERS</div>
                <div style="display:flex;flex-direction:column;gap:4px;font-size:0.88rem;">
                    <div>🥇 Fresh: <strong>{top_fresh_name}</strong> ({top_fresh_val:.0f}")</div>
                    <div>🏔️ Base: <strong>{top_base_name}</strong> ({top_base_val:.0f}")</div>
                    <div>📍 Closest powder: <strong>{closest_powder_text}</strong></div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

    selected_passes = st.multiselect(
        "My pass(es):",
        options=["All"] + ALL_PASSES,
        key="pass_filter",
        help="Filter resorts to only those included on your ski pass(es).",
    )
    if not selected_passes:
        selected_passes = ["All"]

    city_name = st.selectbox(
        "Starting from:",
        options=list(STARTING_CITIES.keys()),
        key="start_city",
    )
    user_lat, user_lon = STARTING_CITIES[city_name]

    sort_by = st.radio(
        "Sort by:",
        options=["🌨️ Fresh Snow", "🏔️ Base Snow", "📍 Distance", "🤖 AI Pick"],
        horizontal=True,
        key="sort_by",
    )

    # ── Quick filter chips ────────────────────────────────────────────────
    st.markdown('<div style="margin-top:8px;margin-bottom:8px;">', unsafe_allow_html=True)
    filter_cols = st.columns(4)

    with filter_cols[0]:
        powder_filter = st.checkbox("⚡ 6\"+ (72h)", key="filter_powder", help="Show only powder days (6\"+ in 72h)")
    with filter_cols[1]:
        base_filter = st.checkbox("🏔️ 50\"+ base", key="filter_base", help="Show only strong base depth (50\"+)")
    with filter_cols[2]:
        distance_filter = st.checkbox("📍 <100mi", key="filter_distance", help="Show only nearby resorts")
    with filter_cols[3]:
        if not _first_load and 'forecasts' in st.session_state:
            forecast_filter = st.checkbox("🔮 4\"+ wknd", key="filter_forecast", help="Show only resorts with 4\"+ weekend forecast")
        else:
            forecast_filter = False

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(
        '<div style="display:flex;align-items:center;gap:8px;margin:6px 0 4px 0;">'
        '<span style="font-size:1.15rem;font-weight:700;letter-spacing:-0.01em;">❄️ Live Conditions</span>'
        '<div style="flex:1;height:1.5px;background:linear-gradient(to right,rgba(99,179,237,0.35),transparent);margin-left:4px;"></div>'
        '</div>',
        unsafe_allow_html=True)

    if _first_load:
        # Placeholder shown while data loads in the background
        _cards_ph = st.empty()
        _cards_ph.markdown(
            '<div style="padding:14px 4px;opacity:0.6;font-size:0.9rem;">⏳ Loading snow conditions…</div>',
            unsafe_allow_html=True)
    else:
        # Recalculate visible with current widget values (user may have changed filter)
        visible = {r: d for r, d in conditions.items() if pass_filter(r, selected_passes)}
        visible = _apply_quick_filters(visible, forecasts, user_lat, user_lon)

        _use_base_map = sort_by == "🏔️ Base Snow"
        _map_scale    = 0.2 if _use_base_map else 2
        _map_floor    = 30 if _use_base_map else 6
        _all_map_vals = [visible[r].get("snow_depth_in" if _use_base_map else "new_snow_72h", 0)
                         if visible[r] else 0 for r in visible]
        _CMAX         = max(max(_all_map_vals, default=0), _map_floor)

        if sort_by == "🤖 AI Pick":
            if "ai_pick_ranking" in st.session_state:
                _rank_map = {r: i for i, r in enumerate(st.session_state["ai_pick_ranking"])}
                _ordered = sorted(visible.items(), key=lambda x: _rank_map.get(x[0], 999))
            else:
                _ordered = sorted(
                    visible.items(),
                    key=lambda x: -(x[1].get("new_snow_72h", 0) if x[1] else 0)
                )
                st.caption("💬 Ask a question to personalise the AI Pick ranking.")
        else:
            def _sort_key(item):
                resort, d = item
                if sort_by == "📍 Distance":
                    return haversine_miles(
                        user_lat, user_lon,
                        RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
                    )
                elif sort_by == "🏔️ Base Snow":
                    return -(d.get("snow_depth_in", 0) if d else 0)
                else:
                    return -(d.get("new_snow_72h", 0) if d else 0)
            _ordered = sorted(visible.items(), key=_sort_key)

        cards_html = []
        for resort, d in _ordered:
            badges = " ".join(_PASS_BADGE[p] for p in resort_passes(resort))
            dist = haversine_miles(
                user_lat, user_lon,
                RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
            )
            if d is None:
                cards_html.append(
                    f'<div class="resort-card">'
                    f'<div class="resort-card-top">'
                    f'<span class="resort-dot" style="color:#5a8fb5">○</span>'
                    f'<span class="resort-name">{resort}</span>{badges}'
                    f'<span class="resort-dist">{dist:.0f} mi</span>'
                    f'</div>'
                    f'<div class="resort-no-data">no SNOTEL — check resort site</div>'
                    f'</div>'
                )
                continue
            new72 = d.get("new_snow_72h", 0)
            base = d.get("snow_depth_in", 0)
            _val = base if _use_base_map else new72
            _t = (_val / _CMAX) if _CMAX > 0 else 0
            dot_color = _blues_color(_t)
            cards_html.append(
                f'<div class="resort-card">'
                f'<div class="resort-card-top">'
                f'<span class="resort-dot" style="color:{dot_color}">●</span>'
                f'<span class="resort-name">{resort}</span>{badges}'
                f'<span class="resort-dist">{dist:.0f} mi</span>'
                f'</div>'
                f'<div class="resort-stats">{new72:.0f}" new (72h) · {base:.0f}" base</div>'
                f'</div>'
            )
        st.markdown("".join(cards_html), unsafe_allow_html=True)

# ── RIGHT: chat ───────────────────────────────────────────────────────────────

with col_right:
    st.markdown("### 💬 Ask the Powracle")
    st.caption(
        "Ask me where to ski, which resort has the best snow, "
        "or how this season compares to average.")

    st.checkbox(
        "Use deterministic answers for simple factual snow questions",
        key="use_deterministic_simple_answers",
        help="When enabled, a narrow set of simple live-data questions (like deepest base or most fresh snow right now) will be answered directly from the data instead of through the LLM.",
    )

    # ── Smart Trip Planner ────────────────────────────────────────────────
    with st.expander("🗓️ Smart Trip Planner", expanded=False):
        st.markdown("Plan a multi-day ski trip with optimal resort recommendations, forecast analysis, and traffic timing.")

        plan_col1, plan_col2 = st.columns(2)
        with plan_col1:
            from datetime import datetime, timedelta
            trip_start = st.date_input(
                "Start date:",
                value=datetime.now() + timedelta(days=3),
                min_value=datetime.now().date(),
                max_value=datetime.now().date() + timedelta(days=14),
                help="When does your trip start?"
            )
        with plan_col2:
            num_days = st.slider(
                "Number of days:",
                min_value=1,
                max_value=7,
                value=3,
                help="How many days will you ski?"
            )

        lodging_pref = st.selectbox(
            "Lodging preference (optional):",
            options=["Flexible", "I-70 Corridor (Vail, Breck, etc.)", "Summit County", "Steamboat", "Aspen/Snowmass", "Wolf Creek area"],
            help="Where do you prefer to stay? This helps optimize driving."
        )

        trip_notes = st.text_area(
            "Additional preferences:",
            placeholder="e.g., 'Avoid I-70 on weekends', 'Prefer tree skiing', 'Looking for steeps'",
            height=60
        )

        if st.button("🎿 Generate Trip Plan", type="primary", use_container_width=True):
            if not _first_load:
                # Build trip planning prompt
                trip_prompt = f"""I'm planning a {num_days}-day ski trip starting {trip_start.strftime('%A, %B %d')}.

REQUIREMENTS:
- Recommend which resorts to visit each day
- Consider the 7-day snow forecast for optimal timing
- Factor in weekend traffic patterns (avoid I-70 Sunday eastbound if possible)
- Suggest best departure times to avoid traffic
"""
                if lodging_pref and lodging_pref != "Flexible":
                    trip_prompt += f"- I'm staying in/near: {lodging_pref}\n"

                if trip_notes.strip():
                    trip_prompt += f"- Additional notes: {trip_notes}\n"

                # Add pass restriction with explicit resort list
                if selected_passes and "All" not in selected_passes:
                    pass_str = " and ".join(selected_passes)
                    valid_resorts = [r for r in RESORT_STATIONS if pass_filter(r, selected_passes)]
                    trip_prompt += f"\n**IMPORTANT**: I have a {pass_str} Pass. You MUST ONLY recommend resorts from this list: {', '.join(valid_resorts)}. Do not recommend any other resorts."
                else:
                    trip_prompt += f"\nMy ski pass(es): Any resort is fine"

                trip_prompt += f"\nStarting from: {city_name}"
                trip_prompt += """

Please provide a day-by-day itinerary in this format:

**Day 1 (Date)** - Resort Name
- Expected snow: X" fresh, Y" base
- Conditions: [weather description]
- Drive time: X hours from [location]
- Departure: Leave by [time] to avoid traffic
- Why: [brief rationale for this choice]

[Continue for each day...]

**Overall Tips:**
[Any additional advice about lodging, traffic, gear, etc.]"""

                # Save trip to database if user is logged in (not guest)
                if db_available and st.session_state.user and isinstance(st.session_state.user, User):
                    try:
                        trip_end = trip_start + timedelta(days=num_days - 1)
                        new_trip = Trip(
                            user_id=st.session_state.user.user_id,
                            trip_name=f"{num_days}-day trip starting {trip_start.strftime('%b %d')}",
                            start_date=trip_start,
                            end_date=trip_end,
                            total_days=num_days,
                            lodging_location=lodging_pref if lodging_pref != "Flexible" else None,
                            notes=trip_notes if trip_notes.strip() else None
                        )

                        with get_db() as db:
                            db.add(new_trip)
                            db.commit()
                            db.refresh(new_trip)

                            # Create placeholder trip days (agent will recommend specific resorts)
                            for i in range(num_days):
                                day_date = trip_start + timedelta(days=i)
                                trip_day = TripDay(
                                    trip_id=new_trip.trip_id,
                                    day_number=i + 1,
                                    date=day_date,
                                    resort_name="TBD",  # Will be updated when user checks in
                                    checked_in=False
                                )
                                db.add(trip_day)
                            db.commit()

                        st.success(f"Trip saved! View it in 'My Trips' page.")
                    except Exception as e:
                        st.warning(f"Trip plan generated but couldn't save to database: {e}")

                # Inject this prompt into the chat
                st.session_state.trip_planner_prompt = trip_prompt
                st.rerun()

    prompt = st.chat_input("Where should I ski this weekend?")

    _chat_container = st.container(height=600, border=False)

    with _chat_container:
        _new_msg_ph = st.empty()

        _old_history = st.session_state.messages

        if not _old_history and not prompt:
            with st.chat_message("assistant"):
                st.markdown(
                    "Hey! I can tell you where the powder is right now, "
                    "which resorts historically get the most snow, and whether "
                    "this season is above or below average. What do you want to know?"
                )

        _pairs = list(zip(_old_history[0::2], _old_history[1::2]))
        for user_msg, asst_msg in reversed(_pairs):
            with st.chat_message(user_msg["role"]):
                st.markdown(user_msg["content"])
            with st.chat_message(asst_msg["role"]):
                st.markdown(asst_msg["content"])

# ── Handle new prompt — data must be loaded ───────────────────────────────────

# Check for trip planner prompt
if "trip_planner_prompt" in st.session_state and not _first_load:
    prompt = st.session_state.trip_planner_prompt
    del st.session_state.trip_planner_prompt

if prompt and not _first_load:
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Detect if this is a trip planning query
    _is_trip_plan = any(keyword in prompt.lower() for keyword in ["trip", "itinerary", "day-by-day", "multi-day", "days starting"])

    # Build live conditions snapshot for all resorts (unrounded so agent is precise)
    _cond_snapshot = "\n".join(
        f"  - {r}: {conditions[r].get('new_snow_72h', 0):.1f}\" new (72h), "
        f"{conditions[r].get('new_snow_48h', 0):.1f}\" new (48h), "
        f"{conditions[r].get('new_snow_24h', 0):.1f}\" new (24h), "
        f"{conditions[r].get('snow_depth_in', 0):.1f}\" base"
        if conditions.get(r) else f"  - {r}: no live data"
        for r in RESORT_STATIONS
    )

    # Build forecast snapshot (enhanced for trip planning)
    if _is_trip_plan:
        # Load full 7-day forecast
        forecasts_7day = load_7day_forecasts()
        _forecast_lines = []
        for r in RESORT_STATIONS:
            if forecasts_7day.get(r):
                daily = " / ".join([f"{f['date'][-5:]}: {f['snowfall_in']:.1f}\"" for f in forecasts_7day[r]])
                _forecast_lines.append(f"  - {r}: {daily}")
            else:
                _forecast_lines.append(f"  - {r}: no forecast")
        _forecast_snapshot = "\n".join(_forecast_lines)
        _forecast_label = "7-day snowfall forecast (Open-Meteo)"
    else:
        _forecast_snapshot = "\n".join(
            f"  - {r}: Sat {forecasts[r]['saturday_snow_in']:.1f}\" / "
            f"Sun {forecasts[r]['sunday_snow_in']:.1f}\" / "
            f"weekend total {forecasts[r]['weekend_total_in']:.1f}\""
            if forecasts.get(r) else f"  - {r}: no forecast"
            for r in RESORT_STATIONS
        )
        _forecast_label = "Weekend snowfall forecast (Open-Meteo)"

    # Add traffic/distance context for trip planning
    if _is_trip_plan:
        _distance_info = "\n".join(
            f"  - {r}: {haversine_miles(user_lat, user_lon, RESORT_STATIONS[r]['lat'], RESORT_STATIONS[r]['lon']):.0f} mi from {city_name}"
            for r in RESORT_STATIONS
        )
        _traffic_tips = """
[Traffic patterns to consider:]
  - Saturday AM westbound I-70: heavy 6-10am (leave early or late)
  - Sunday PM eastbound I-70: very heavy 1-6pm (leave before noon or after 7pm)
  - US-40 and US-285 are slower but less crowded alternatives
  - Chain laws can add 30-60min delay during storms"""

        _context = (
            f"[Live snowpack for all resorts right now:\n{_cond_snapshot}]\n\n"
            f"[{_forecast_label}:\n{_forecast_snapshot}]\n\n"
            f"[Distances from {city_name}:\n{_distance_info}]\n\n"
            f"{_traffic_tips}\n\n"
        )
    else:
        _context = (
            f"[Live snowpack for all resorts right now:\n{_cond_snapshot}]\n\n"
            f"[{_forecast_label}:\n{_forecast_snapshot}]\n\n"
        )

    if selected_passes and "All" not in selected_passes:
        pass_str = " and ".join(selected_passes)
        pass_resorts = [r for r in RESORT_STATIONS
                        if pass_filter(r, selected_passes)]
        agent_prompt = (
            _context
            + f"[User context: I have a {pass_str} Pass. "
            f"Only recommend resorts on my pass: {', '.join(pass_resorts)}.]\n\n"
            + prompt
        )
    else:
        agent_prompt = _context + prompt

    # Write new exchange into the top placeholder inside _chat_container
    with _new_msg_ph.container():
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Checking the snowpack..."):
                print(f"\n\033[1mQuestion:\033[0m {prompt}")

                simple_result = None
                if st.session_state.get("use_deterministic_simple_answers", False) and not _is_trip_plan:
                    simple_result = try_answer_simple_live_question(
                        question=prompt,
                        conditions=conditions,
                        selected_passes=selected_passes,
                        resort_stations=RESORT_STATIONS,
                        pass_filter_fn=pass_filter,
                    )

                if simple_result is not None:
                    response_display = simple_result["answer"]

                    st.markdown(response_display)

                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_display}
                    )

                    st.session_state["ai_pick_ranking"] = simple_result["ranking"]
                else:
                    chat_result = run_chat_turn(
                        agent=st.session_state.agent,
                        messages=st.session_state.messages,
                        agent_prompt=agent_prompt,
                        resort_names=list(RESORT_STATIONS.keys()),
                    )

                    response_display = chat_result["response_display"]

                    st.markdown(response_display)

                    st.session_state.messages.append(
                        {"role": "assistant", "content": response_display}
                    )

                    st.session_state["ai_pick_ranking"] = chat_result["ranking"]

                # Rerun so the left column reflects the new ranking immediately
                if sort_by == "🤖 AI Pick":
                    st.rerun()

# ── First load: fetch data, fill cards placeholder, then rerun to show map ────

if _first_load:
    with _TPE(max_workers=2) as _pool:
        _f_cond = _pool.submit(load_conditions)
        _f_fore = _pool.submit(load_forecasts)
        st.session_state.conditions = _f_cond.result()
        st.session_state.forecasts  = _f_fore.result()

    conditions = st.session_state.conditions
    forecasts  = st.session_state.forecasts

    # Compute cards with seed widget values (Denver / Fresh Snow / All)
    _visible_fl = {r: d for r, d in conditions.items() if pass_filter(r, selected_passes)}
    _use_base_fl = sort_by == "🏔️ Base Snow"
    _field_fl   = "snow_depth_in" if _use_base_fl else "new_snow_72h"
    _floor_fl   = 30 if _use_base_fl else 6
    _vals_fl    = [_visible_fl[r].get(_field_fl, 0) if _visible_fl[r] else 0 for r in _visible_fl]
    _CMAX_fl    = max(max(_vals_fl, default=0), _floor_fl)

    # Default sort: fresh snow descending
    _ordered_fl = sorted(
        _visible_fl.items(),
        key=lambda x: -(x[1].get("new_snow_72h", 0) if x[1] else 0)
    )

    _cards_fl = []
    for resort, d in _ordered_fl:
        badges = " ".join(_PASS_BADGE[p] for p in resort_passes(resort))
        dist = haversine_miles(
            user_lat, user_lon,
            RESORT_STATIONS[resort]["lat"], RESORT_STATIONS[resort]["lon"]
        )
        if d is None:
            _cards_fl.append(
                f'<div class="resort-card">'
                f'<div class="resort-card-top">'
                f'<span class="resort-dot" style="color:#5a8fb5">○</span>'
                f'<span class="resort-name">{resort}</span>{badges}'
                f'<span class="resort-dist">{dist:.0f} mi</span>'
                f'</div>'
                f'<div class="resort-no-data">no SNOTEL — check resort site</div>'
                f'</div>'
            )
            continue
        new72 = d.get("new_snow_72h", 0)
        base  = d.get("snow_depth_in", 0)
        _val  = base if _use_base_fl else new72
        _t    = (_val / _CMAX_fl) if _CMAX_fl > 0 else 0
        _cards_fl.append(
            f'<div class="resort-card">'
            f'<div class="resort-card-top">'
            f'<span class="resort-dot" style="color:{_blues_color(_t)}">●</span>'
            f'<span class="resort-name">{resort}</span>{badges}'
            f'<span class="resort-dist">{dist:.0f} mi</span>'
            f'</div>'
            f'<div class="resort-stats">{new72:.0f}" new (72h) · {base:.0f}" base</div>'
            f'</div>'
        )

    _cards_ph.markdown("".join(_cards_fl), unsafe_allow_html=True)
    st.rerun()
