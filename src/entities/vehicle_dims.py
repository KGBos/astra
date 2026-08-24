"""
Canonical vehicle dimensions in meters (length x width x height).
Single source of truth — consumed by Vehicle sprite construction.
"""

VEHICLE_DIMS = {
    "TAXI":         {"length_m": 4.6, "width_m": 1.85, "height_m": 1.5},
    "CYBER_SEDAN":  {"length_m": 4.8, "width_m": 1.9,  "height_m": 1.45},
    "POLICE":       {"length_m": 4.9, "width_m": 1.95, "height_m": 1.7},
    "BUS":          {"length_m": 11.9, "width_m": 2.55, "height_m": 3.0},
}
