"""
Pass ROI Calculator

Calculates how much money users save by having a season pass
vs. buying individual lift tickets.
"""

from datetime import datetime, date
from decimal import Decimal
from models.user import UserPass, TripDay, ResortTicketPrice, UserSeasonStats
from db.postgres import get_db


class ROICalculator:
    """Calculate return on investment for ski passes"""

    @staticmethod
    def get_current_season() -> str:
        """
        Get current ski season string (e.g., '2024-2025')
        Season runs Nov-Apr
        """
        now = datetime.now()
        month = now.month
        year = now.year

        if month >= 11:  # November or December
            return f"{year}-{year+1}"
        else:  # Jan-Oct
            return f"{year-1}-{year}"

    @staticmethod
    def is_weekend(check_date: date) -> bool:
        """Check if date is a weekend (Saturday=5, Sunday=6)"""
        return check_date.weekday() in [5, 6]

    @staticmethod
    def calculate_ticket_value(resort_name: str, visit_date: date, season: str = None) -> Decimal:
        """
        Calculate the value of a single lift ticket for this resort/date.

        Uses peak pricing for weekends/holidays, regular pricing for weekdays.
        """
        if season is None:
            season = ROICalculator.get_current_season()

        try:
            with get_db() as db:
                price_info = db.query(ResortTicketPrice).filter(
                    ResortTicketPrice.resort_name == resort_name
                ).first()

                if not price_info:
                    # Default fallback pricing if resort not in database
                    return Decimal(150.00) if ROICalculator.is_weekend(visit_date) else Decimal(120.00)

                # Use peak price for weekends, regular price for weekdays
                if ROICalculator.is_weekend(visit_date):
                    return price_info.peak_price
                else:
                    return price_info.regular_price

        except Exception as e:
            print(f"Error fetching ticket price: {e}")
            return Decimal(150.00)  # Default fallback

    @staticmethod
    def calculate_user_roi(user_id: str, season: str = None) -> dict:
        """
        Calculate ROI for a user's season pass.

        Returns:
            {
                'days_skied': int,
                'total_pass_cost': Decimal,
                'total_ticket_value': Decimal,
                'roi': Decimal,  # Amount saved
                'roi_percentage': float,
                'break_even_days': int,  # Days needed to break even
                'resorts_visited': list[str],
                'unique_resorts': int,
                'best_value_day': (date, resort, value),
            }
        """
        if season is None:
            season = ROICalculator.get_current_season()

        try:
            with get_db() as db:
                # Get user's passes for this season
                passes = db.query(UserPass).filter(
                    UserPass.user_id == user_id,
                    UserPass.valid_from <= datetime.now().date(),
                    UserPass.valid_until >= datetime.now().date()
                ).all()

                if not passes:
                    return {
                        'days_skied': 0,
                        'total_pass_cost': Decimal(0),
                        'total_ticket_value': Decimal(0),
                        'roi': Decimal(0),
                        'roi_percentage': 0.0,
                        'break_even_days': 0,
                        'resorts_visited': [],
                        'unique_resorts': 0,
                        'best_value_day': None,
                    }

                # Sum up pass costs
                total_pass_cost = sum(p.purchase_price for p in passes)

                # Get all checked-in trip days for this season
                # We need to join through trips to filter by season dates
                from models.user import Trip

                season_start = datetime.strptime(f"{season.split('-')[0]}-11-01", "%Y-%m-%d").date()
                season_end = datetime.strptime(f"{season.split('-')[1]}-05-31", "%Y-%m-%d").date()

                trip_days = db.query(TripDay).join(Trip).filter(
                    Trip.user_id == user_id,
                    TripDay.checked_in == True,
                    TripDay.date >= season_start,
                    TripDay.date <= season_end
                ).all()

                # Calculate ticket values
                total_ticket_value = Decimal(0)
                resorts_visited = []
                best_value_day = None
                max_value = Decimal(0)

                for day in trip_days:
                    ticket_value = ROICalculator.calculate_ticket_value(
                        day.resort_name,
                        day.date,
                        season
                    )
                    total_ticket_value += ticket_value
                    resorts_visited.append(day.resort_name)

                    if ticket_value > max_value:
                        max_value = ticket_value
                        best_value_day = (day.date, day.resort_name, ticket_value)

                # Calculate ROI
                roi = total_ticket_value - total_pass_cost
                roi_percentage = float((roi / total_pass_cost * 100)) if total_pass_cost > 0 else 0.0

                # Calculate break-even (assuming average ticket price)
                avg_ticket_price = total_ticket_value / len(trip_days) if trip_days else Decimal(150)
                break_even_days = int(total_pass_cost / avg_ticket_price) if avg_ticket_price > 0 else 0

                return {
                    'days_skied': len(trip_days),
                    'total_pass_cost': total_pass_cost,
                    'total_ticket_value': total_ticket_value,
                    'roi': roi,
                    'roi_percentage': roi_percentage,
                    'break_even_days': break_even_days,
                    'resorts_visited': resorts_visited,
                    'unique_resorts': len(set(resorts_visited)),
                    'best_value_day': best_value_day,
                }

        except Exception as e:
            print(f"Error calculating ROI: {e}")
            return {
                'days_skied': 0,
                'total_pass_cost': Decimal(0),
                'total_ticket_value': Decimal(0),
                'roi': Decimal(0),
                'roi_percentage': 0.0,
                'break_even_days': 0,
                'resorts_visited': [],
                'unique_resorts': 0,
                'best_value_day': None,
            }

    @staticmethod
    def update_season_stats(user_id: str, season: str = None):
        """
        Update cached season statistics in database.

        Should be called after trips are added/modified.
        """
        if season is None:
            season = ROICalculator.get_current_season()

        roi_data = ROICalculator.calculate_user_roi(user_id, season)

        try:
            with get_db() as db:
                # Find or create season stats record
                stats = db.query(UserSeasonStats).filter(
                    UserSeasonStats.user_id == user_id,
                    UserSeasonStats.season == season
                ).first()

                if not stats:
                    stats = UserSeasonStats(user_id=user_id, season=season)
                    db.add(stats)

                # Update stats
                stats.days_skied = roi_data['days_skied']
                stats.resorts_visited = len(roi_data['resorts_visited'])
                stats.unique_resorts = roi_data['unique_resorts']
                stats.pass_roi = roi_data['roi']
                stats.total_lift_ticket_value = roi_data['total_ticket_value']
                stats.total_pass_cost = roi_data['total_pass_cost']

                if roi_data['best_value_day']:
                    stats.best_powder_day = roi_data['best_value_day'][0]
                    stats.favorite_resort = roi_data['best_value_day'][1]

                stats.last_updated = datetime.utcnow()

                db.commit()

                return True

        except Exception as e:
            print(f"Error updating season stats: {e}")
            return False
