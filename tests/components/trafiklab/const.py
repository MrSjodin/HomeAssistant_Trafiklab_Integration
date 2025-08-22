DOMAIN = "trafiklab"

ENTRY_DATA_DEPARTURE = {
    "api_key": "test-key",
    "stop_id": "740098000",
    "name": "Test Stop",
    "sensor_type": "departure",
}

ENTRY_DATA_ARRIVAL = {
    "api_key": "test-key",
    "stop_id": "740098000",
    "name": "Test Stop",
    "sensor_type": "arrival",
}

ENTRY_DATA_RESROBOT = {
    "api_key": "test-key",
    "name": "Travel Sensor",
    "sensor_type": "resrobot_travel_search",
    "origin_type": "stop_id",
    "origin": "740000001",
    "destination_type": "stop_id",
    "destination": "740000002",
}

ENTRY_OPTIONS_DEFAULT = {
    "line_filter": "",
    "direction": "",
    "time_window": 60,
    "refresh_interval": 300,
}

ENTRY_OPTIONS_RESROBOT = {
    "via": "",
    "avoid": "",
    "max_walking_distance": 1000,
    "time_window": 60,
    "refresh_interval": 300,
}
