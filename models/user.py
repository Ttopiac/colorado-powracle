"""
SQLAlchemy models for user accounts and personalization
"""

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Numeric, Date, Text, ForeignKey, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import uuid

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    username = Column(String(50), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)

    # Profile
    home_city = Column(String(100), default='Denver')
    ski_ability = Column(String(20))
    preferred_terrain = Column(Text)  # comma-separated

    # Relationships
    passes = relationship("UserPass", back_populates="user", cascade="all, delete-orphan")
    favorites = relationship("FavoriteResort", back_populates="user", cascade="all, delete-orphan")
    trips = relationship("Trip", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    season_stats = relationship("UserSeasonStats", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"


class UserPass(Base):
    __tablename__ = 'user_passes'

    user_pass_id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    pass_type = Column(String(20), nullable=False)  # IKON, EPIC, INDY
    pass_tier = Column(String(50), nullable=False)  # Full, Base, 4-Day
    purchase_price = Column(Numeric(10, 2), nullable=False)
    valid_from = Column(Date, nullable=False)
    valid_until = Column(Date, nullable=False)
    days_used = Column(Integer, default=0)
    days_total = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="passes")

    def __repr__(self):
        return f"<UserPass(type='{self.pass_type}', tier='{self.pass_tier}')>"


class FavoriteResort(Base):
    __tablename__ = 'favorite_resorts'

    favorite_id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    resort_name = Column(String(100), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    user = relationship("User", back_populates="favorites")

    def __repr__(self):
        return f"<FavoriteResort(resort='{self.resort_name}')>"


class Trip(Base):
    __tablename__ = 'trips'

    trip_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    trip_name = Column(String(200), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    total_days = Column(Integer, nullable=False)
    lodging_location = Column(String(200))
    notes = Column(Text)

    user = relationship("User", back_populates="trips")
    days = relationship("TripDay", back_populates="trip", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Trip(name='{self.trip_name}', days={self.total_days})>"


class TripDay(Base):
    __tablename__ = 'trip_days'

    trip_day_id = Column(Integer, primary_key=True)
    trip_id = Column(UUID(as_uuid=True), ForeignKey('trips.trip_id', ondelete='CASCADE'), nullable=False)
    day_number = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    resort_name = Column(String(100), nullable=False)

    # Check-in
    checked_in = Column(Boolean, default=False)
    check_in_time = Column(DateTime)

    # Ratings
    rating = Column(Integer)
    review = Column(Text)

    # Actual conditions
    actual_snow_in = Column(Numeric(5, 1))
    actual_weather = Column(String(50))

    trip = relationship("Trip", back_populates="days")

    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='valid_rating'),
    )

    def __repr__(self):
        return f"<TripDay(resort='{self.resort_name}', date={self.date})>"


class UserSettings(Base):
    __tablename__ = 'user_settings'

    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), primary_key=True)
    default_sort = Column(String(20), default='Fresh Snow')
    show_snowfall_effect = Column(Boolean, default=False)
    email_notifications = Column(Boolean, default=True)
    powder_alert_threshold = Column(Integer, default=6)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<UserSettings(user_id='{self.user_id}')>"


class UserSeasonStats(Base):
    __tablename__ = 'user_season_stats'

    stat_id = Column(Integer, primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    season = Column(String(9), nullable=False)

    # Usage
    days_skied = Column(Integer, default=0)
    resorts_visited = Column(Integer, default=0)
    unique_resorts = Column(Integer, default=0)

    # Financial ROI
    pass_roi = Column(Numeric(10, 2), default=0)
    total_lift_ticket_value = Column(Numeric(10, 2), default=0)
    total_pass_cost = Column(Numeric(10, 2), default=0)

    # Highlights
    favorite_resort = Column(String(100))
    best_powder_day = Column(Date)
    max_snow_day = Column(Numeric(5, 1))

    last_updated = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="season_stats")

    def __repr__(self):
        return f"<UserSeasonStats(season='{self.season}', days={self.days_skied})>"


class ResortTicketPrice(Base):
    __tablename__ = 'resort_ticket_prices'

    resort_name = Column(String(100), primary_key=True)
    peak_price = Column(Numeric(6, 2), nullable=False)
    regular_price = Column(Numeric(6, 2), nullable=False)
    season = Column(String(9), nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ResortTicketPrice(resort='{self.resort_name}', peak=${self.peak_price})>"
