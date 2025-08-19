"""Constants for the Trafiklab integration."""
from typing import Final

DOMAIN: Final = "trafiklab"

# Configuration keys
CONF_API_KEY: Final = "api_key"
CONF_STOP_ID: Final = "stop_id"
CONF_SITE_ID: Final = "site_id"
CONF_LINE_NUMBER: Final = "line_number"
CONF_LINE_FILTER: Final = "line_filter"
CONF_DIRECTION: Final = "direction"
CONF_TRANSPORT_MODE: Final = "transport_mode"
CONF_SENSOR_TYPE: Final = "sensor_type"
CONF_TIME_WINDOW: Final = "time_window"
CONF_REFRESH_INTERVAL: Final = "refresh_interval"
CONF_UPDATE_CONDITION: Final = "update_condition"

# Sensor types
SENSOR_TYPE_DEPARTURE: Final = "departure"
SENSOR_TYPE_ARRIVAL: Final = "arrival"

# Default values
DEFAULT_SCAN_INTERVAL: Final = 300  # 5 minutes in seconds
MINIMUM_SCAN_INTERVAL: Final = 60   # 1 minute minimum
DEFAULT_NAME: Final = "Trafiklab"
DEFAULT_TIME_WINDOW: Final = 60  # minutes
DEFAULT_UPDATE_CONDITION: Final = ""  # empty means always update

# API endpoints
API_BASE_URL: Final = "https://realtime-api.trafiklab.se/v1"
DEPARTURES_ENDPOINT: Final = "/departures"
ARRIVALS_ENDPOINT: Final = "/arrivals"
STOP_LOOKUP_ENDPOINT: Final = "/stops/name"

# Transport modes
TRANSPORT_MODES = {
    "bus": "BUS",
    "metro": "METRO", 
    "train": "TRAIN",
    "tram": "TRAM",
    "ship": "SHIP"
}

# Service names
SERVICE_STOP_LOOKUP: Final = "stop_lookup"

# Service fields
ATTR_SEARCH_QUERY: Final = "search_query"
ATTR_STOPS_FOUND: Final = "stops_found"

# Attributes
ATTR_STOP_NAME: Final = "stop_name"
ATTR_LINE: Final = "line"
ATTR_DESTINATION: Final = "destination"
ATTR_DIRECTION: Final = "direction"
ATTR_EXPECTED_TIME: Final = "expected_time"
ATTR_REAL_TIME: Final = "real_time"
ATTR_TRANSPORT_MODE: Final = "transport_mode"
ATTR_DEVIATIONS: Final = "deviations"
ATTR_LINE: Final = "line"
ATTR_DESTINATION: Final = "destination"
ATTR_DIRECTION: Final = "direction"
ATTR_EXPECTED_TIME: Final = "expected_time"
ATTR_REAL_TIME: Final = "real_time"
ATTR_TRANSPORT_MODE: Final = "transport_mode"
ATTR_DEVIATIONS: Final = "deviations"

# Error messages
ERROR_API_KEY_INVALID: Final = "Invalid API key"
ERROR_STOP_NOT_FOUND: Final = "Stop not found"
ERROR_CONNECTION: Final = "Connection error"
