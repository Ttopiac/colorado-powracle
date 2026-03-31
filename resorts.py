# Colorado ski resort → SNOTEL station mapping.
#
# snotel_quality:
#   "good" — station is on-mountain or <5mi, same terrain character
#   "fair" — station is a reasonable proxy (5–15mi, similar elevation)
#   "none" — no usable SNOTEL nearby; agent uses web_search for snowpack
#
# Station IDs verified via SNOTEL REST API stationTriplet lookup.

RESORT_STATIONS = {

    # ── IKON PASS ─────────────────────────────────────────────────────────────

    "Steamboat Springs": {
        "station_id":    "457:CO:SNTL",
        "station_name":  "Dry Lake",
        "snotel_quality": "good",    # 3mi NE of resort, same ridge
        "corridor":      "US-40",
        "pass":          ["IKON"],
        "lat": 40.4572, "lon": -106.8045,
    },
    "Winter Park": {
        "station_id":    "335:CO:SNTL",
        "station_name":  "Berthoud Summit",
        "snotel_quality": "good",    # on the pass above the resort
        "corridor":      "US-40",
        "pass":          ["IKON"],
        "lat": 39.8868, "lon": -105.7625,
    },
    "Copper Mountain": {
        "station_id":    "415:CO:SNTL",
        "station_name":  "Copper Mountain",
        "snotel_quality": "good",    # on-mountain
        "corridor":      "I-70",
        "pass":          ["IKON"],
        "lat": 39.5022, "lon": -106.1497,
    },
    "Arapahoe Basin": {
        "station_id":    "531:CO:SNTL",
        "station_name":  "Hoosier Pass",
        "snotel_quality": "good",    # same Continental Divide saddle
        "corridor":      "I-70",
        "pass":          ["IKON"],
        "lat": 39.6422, "lon": -105.8719,
    },
    "Aspen / Snowmass": {
        "station_id":    "542:CO:SNTL",
        "station_name":  "Independence Pass",
        "snotel_quality": "good",    # on the pass, same watershed
        "corridor":      "I-70 then CO-82",
        "pass":          ["IKON"],
        "lat": 39.2084, "lon": -106.9490,
    },
    "Eldora": {
        "station_id":    "335:CO:SNTL",
        "station_name":  "Berthoud Summit",
        "snotel_quality": "fair",    # ~8mi, adjacent terrain but different drainage
        "corridor":      "CO-119",
        "pass":          ["IKON"],
        "lat": 39.9378, "lon": -105.5820,
    },

    # ── EPIC PASS ─────────────────────────────────────────────────────────────

    "Breckenridge": {
        "station_id":    "531:CO:SNTL",
        "station_name":  "Hoosier Pass",
        "snotel_quality": "good",    # on the Continental Divide above resort
        "corridor":      "I-70",
        "pass":          ["EPIC"],
        "lat": 39.4800, "lon": -106.0667,
    },
    "Vail": {
        "station_id":    "842:CO:SNTL",
        "station_name":  "Vail Mountain",
        "snotel_quality": "good",    # on-mountain
        "corridor":      "I-70",
        "pass":          ["EPIC"],
        "lat": 39.6433, "lon": -106.3781,
    },
    "Beaver Creek": {
        "station_id":    "1041:CO:SNTL",
        "station_name":  "Beaver Ck Village",
        "snotel_quality": "good",    # 1mi from resort base, confirmed via API
        "corridor":      "I-70",
        "pass":          ["EPIC"],
        "lat": 39.6042, "lon": -106.5169,
    },
    "Keystone": {
        "station_id":    "531:CO:SNTL",
        "station_name":  "Hoosier Pass",
        "snotel_quality": "good",    # same pass as Breckenridge, ~5mi
        "corridor":      "I-70",
        "pass":          ["EPIC"],
        "lat": 39.6061, "lon": -105.9533,
    },
    "Crested Butte": {
        "station_id":    "380:CO:SNTL",
        "station_name":  "Butte",
        "snotel_quality": "good",    # on the mountain above town
        "corridor":      "US-285 then CO-135",
        "pass":          ["EPIC"],
        "lat": 38.8697, "lon": -106.9878,
    },
    "Telluride": {
        "station_id":    "586:CO:SNTL",
        "station_name":  "Lizard Head Pass",
        "snotel_quality": "good",    # on the pass, same San Juan massif
        "corridor":      "US-285 then US-550",
        "pass":          ["EPIC"],
        "lat": 37.9375, "lon": -107.8123,
    },

    # ── INDY PASS ─────────────────────────────────────────────────────────────

    "Loveland": {
        "station_id":    "602:CO:SNTL",
        "station_name":  "Loveland Basin",
        "snotel_quality": "good",    # on the ski area
        "corridor":      "I-70",
        "pass":          ["INDY"],
        "lat": 39.6797, "lon": -105.8975,
    },
    "Wolf Creek": {
        "station_id":    "874:CO:SNTL",
        "station_name":  "Wolf Creek Summit",
        "snotel_quality": "good",    # 0mi — literally at the summit
        "corridor":      "US-160",
        "pass":          ["INDY"],
        "lat": 37.4767, "lon": -106.7964,
    },
    "Monarch Mountain": {
        "station_id":    "701:CO:SNTL",
        "station_name":  "Porphyry Creek",
        "snotel_quality": "good",    # 2mi from resort, same drainage
        "corridor":      "US-50",
        "pass":          ["INDY"],
        "lat": 38.5192, "lon": -106.3317,
    },
    "Ski Cooper": {
        "station_id":    "485:CO:SNTL",
        "station_name":  "Fremont Pass",
        "snotel_quality": "fair",    # 10mi north, similar elevation (~11k ft)
        "corridor":      "US-24",
        "pass":          ["INDY"],
        "lat": 39.3597, "lon": -106.3484,
    },
    "Purgatory": {
        "station_id":    "387:CO:SNTL",
        "station_name":  "Cascade #2",
        "snotel_quality": "fair",    # 5mi east, same San Juan range
        "corridor":      "US-550",
        "pass":          ["INDY"],
        "lat": 37.6325, "lon": -107.8683,
    },
    "Powderhorn": {
        "station_id":    "622:CO:SNTL",
        "station_name":  "Mesa Lakes",
        "snotel_quality": "fair",    # 3mi, but Grand Mesa plateau terrain differs
        "corridor":      "I-70 then CO-65",
        "pass":          ["INDY"],
        "lat": 39.0742, "lon": -108.0233,
    },
    "Sunlight Mountain": {
        "station_id":    None,
        "station_name":  None,
        "snotel_quality": "none",    # nearest SNTL is 20+ miles away in a different range
        "corridor":      "I-70 then CO-82",
        "pass":          ["INDY"],
        "lat": 39.4678, "lon": -107.3653,
    },
}


# ── Shared helpers (used by app.py and api.py) ───────────────────────────────

ALL_PASSES = ["IKON", "EPIC", "INDY"]

STARTING_CITIES = {
    "Denver":           (39.7392, -104.9903),
    "Boulder":          (40.0150, -105.2705),
    "Colorado Springs": (38.8339, -104.8214),
    "Fort Collins":     (40.5853, -105.0844),
    "Pueblo":           (38.2544, -104.6091),
    "Grand Junction":   (39.0639, -108.5506),
}


def resort_passes(resort: str) -> list[str]:
    return RESORT_STATIONS[resort].get("pass", [])


def pass_filter(resort: str, selected: list[str]) -> bool:
    """True if resort should be shown given the selected pass list."""
    if not selected or "All" in selected:
        return True
    return any(p in resort_passes(resort) for p in selected)
