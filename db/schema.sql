-- Colorado Powracle - User Accounts & Personalization Schema
-- No image storage - pure data tracking for ROI and personalization

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,

    -- Profile fields
    home_city VARCHAR(100) DEFAULT 'Denver',
    ski_ability VARCHAR(20) CHECK (ski_ability IN ('Beginner', 'Intermediate', 'Advanced', 'Expert')),
    preferred_terrain TEXT, -- comma-separated: groomers,trees,bowls,steeps

    CONSTRAINT valid_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

-- User ski passes (many-to-many: user can have multiple passes)
CREATE TABLE IF NOT EXISTS user_passes (
    user_pass_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    pass_type VARCHAR(20) NOT NULL CHECK (pass_type IN ('IKON', 'EPIC', 'INDY')),
    pass_tier VARCHAR(50) NOT NULL, -- 'Full', 'Base', '4-Day', etc.
    purchase_price DECIMAL(10,2) NOT NULL, -- What they paid for the pass
    valid_from DATE NOT NULL,
    valid_until DATE NOT NULL,
    days_used INTEGER DEFAULT 0,
    days_total INTEGER,

    created_at TIMESTAMP DEFAULT NOW()
);

-- Favorite resorts
CREATE TABLE IF NOT EXISTS favorite_resorts (
    favorite_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    resort_name VARCHAR(100) NOT NULL,
    added_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,

    UNIQUE(user_id, resort_name)
);

-- Trip plans (created from trip planner or manual entry)
CREATE TABLE IF NOT EXISTS trips (
    trip_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    trip_name VARCHAR(200) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),

    -- Trip metadata
    total_days INTEGER NOT NULL,
    lodging_location VARCHAR(200),
    notes TEXT
);

-- Daily trip entries
CREATE TABLE IF NOT EXISTS trip_days (
    trip_day_id SERIAL PRIMARY KEY,
    trip_id UUID REFERENCES trips(trip_id) ON DELETE CASCADE,
    day_number INTEGER NOT NULL,
    date DATE NOT NULL,
    resort_name VARCHAR(100) NOT NULL,

    -- Did they actually go?
    checked_in BOOLEAN DEFAULT FALSE,
    check_in_time TIMESTAMP,

    -- User ratings (filled in after the day)
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    review TEXT,

    -- Actual conditions that day
    actual_snow_in DECIMAL(5,1),
    actual_weather VARCHAR(50),

    UNIQUE(trip_id, day_number)
);

-- User settings
CREATE TABLE IF NOT EXISTS user_settings (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,

    -- UI preferences
    default_sort VARCHAR(20) DEFAULT 'Fresh Snow',
    show_snowfall_effect BOOLEAN DEFAULT FALSE,

    -- Notification preferences (for future)
    email_notifications BOOLEAN DEFAULT TRUE,
    powder_alert_threshold INTEGER DEFAULT 6,

    updated_at TIMESTAMP DEFAULT NOW()
);

-- Season statistics (computed/cached for performance)
CREATE TABLE IF NOT EXISTS user_season_stats (
    stat_id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    season VARCHAR(9) NOT NULL, -- '2024-2025'

    -- Usage stats
    days_skied INTEGER DEFAULT 0,
    resorts_visited INTEGER DEFAULT 0,
    unique_resorts INTEGER DEFAULT 0,

    -- Financial tracking
    pass_roi DECIMAL(10,2) DEFAULT 0, -- Money saved vs buying day tickets
    total_lift_ticket_value DECIMAL(10,2) DEFAULT 0,
    total_pass_cost DECIMAL(10,2) DEFAULT 0,

    -- Best moments
    favorite_resort VARCHAR(100),
    best_powder_day DATE,
    max_snow_day DECIMAL(5,1),

    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, season)
);

-- Lift ticket prices (for ROI calculation)
-- These are approximate walk-up window prices
CREATE TABLE IF NOT EXISTS resort_ticket_prices (
    resort_name VARCHAR(100) PRIMARY KEY,
    peak_price DECIMAL(6,2) NOT NULL, -- Weekend/holiday price
    regular_price DECIMAL(6,2) NOT NULL, -- Weekday price
    season VARCHAR(9) NOT NULL, -- '2024-2025'
    last_updated TIMESTAMP DEFAULT NOW()
);

-- Insert current season ticket prices (2024-2025 estimates)
INSERT INTO resort_ticket_prices (resort_name, peak_price, regular_price, season) VALUES
    ('Vail', 239.00, 209.00, '2024-2025'),
    ('Breckenridge', 229.00, 199.00, '2024-2025'),
    ('Keystone', 199.00, 169.00, '2024-2025'),
    ('Beaver Creek', 249.00, 219.00, '2024-2025'),
    ('Crested Butte', 199.00, 169.00, '2024-2025'),
    ('Winter Park', 209.00, 179.00, '2024-2025'),
    ('Steamboat', 209.00, 179.00, '2024-2025'),
    ('Aspen Snowmass', 219.00, 189.00, '2024-2025'),
    ('Telluride', 189.00, 159.00, '2024-2025'),
    ('Copper Mountain', 199.00, 169.00, '2024-2025'),
    ('Arapahoe Basin', 159.00, 139.00, '2024-2025'),
    ('Loveland', 139.00, 119.00, '2024-2025'),
    ('Monarch', 109.00, 99.00, '2024-2025'),
    ('Wolf Creek', 119.00, 99.00, '2024-2025'),
    ('Eldora', 149.00, 129.00, '2024-2025'),
    ('Sunlight Mountain', 99.00, 89.00, '2024-2025'),
    ('Powderhorn', 99.00, 89.00, '2024-2025'),
    ('Silverton', 159.00, 159.00, '2024-2025'),
    ('Purgatory', 169.00, 149.00, '2024-2025')
ON CONFLICT (resort_name) DO NOTHING;

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_trips_user_date ON trips(user_id, start_date DESC);
CREATE INDEX IF NOT EXISTS idx_trip_days_trip ON trip_days(trip_id, day_number);
CREATE INDEX IF NOT EXISTS idx_trip_days_checked_in ON trip_days(user_id, checked_in) WHERE checked_in = true;
CREATE INDEX IF NOT EXISTS idx_favorites_user ON favorite_resorts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_passes_user ON user_passes(user_id);
CREATE INDEX IF NOT EXISTS idx_season_stats_user ON user_season_stats(user_id, season);

-- Function to calculate current season
CREATE OR REPLACE FUNCTION get_current_season() RETURNS VARCHAR AS $$
DECLARE
    current_month INTEGER;
    current_year INTEGER;
    season VARCHAR(9);
BEGIN
    current_month := EXTRACT(MONTH FROM CURRENT_DATE);
    current_year := EXTRACT(YEAR FROM CURRENT_DATE);

    -- Season runs Nov-Apr (e.g., 2024-2025 season starts Nov 2024)
    IF current_month >= 11 THEN
        season := current_year || '-' || (current_year + 1);
    ELSE
        season := (current_year - 1) || '-' || current_year;
    END IF;

    RETURN season;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update user last_login
CREATE OR REPLACE FUNCTION update_last_login()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_login := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: Trigger creation will happen in migration, not here
