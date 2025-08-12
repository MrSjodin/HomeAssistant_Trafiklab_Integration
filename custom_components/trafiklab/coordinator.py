"""Data update coordinator for Trafiklab."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_SENSOR_TYPE,
    CONF_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_DEPARTURE,
)
from .api import TrafikLabApiClient

_LOGGER = logging.getLogger(__name__)


class TrafikLabCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Trafiklab."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.api_client = TrafikLabApiClient(entry.data[CONF_API_KEY])
        # Track last successful update (UTC ISO8601)
        self.last_successful_update: str | None = None

        # Options override data if present
        refresh_interval = entry.options.get(
            CONF_REFRESH_INTERVAL,
            entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL),
        )
        
        super().__init__(
            hass,
            _LOGGER,
            name="Trafiklab",
            update_interval=timedelta(seconds=refresh_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Trafiklab API."""
        try:
            # Merge data + options (options override)
            # Base immutable data lives in entry.data (api key, stop id, sensor_type, name)
            # Mutable settings now live in options (migration safe fallback to data)
            stop_id = self.entry.data[CONF_STOP_ID]
            sensor_type = self.entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DEPARTURE)
            
            _LOGGER.debug("Fetching %s for stop %s", sensor_type, stop_id)
            
            if sensor_type == SENSOR_TYPE_ARRIVAL:
                data = await self.api_client.get_arrivals(stop_id)
            else:
                data = await self.api_client.get_departures(stop_id)
            
            if not data:
                _LOGGER.warning("No data received from API")
                raise UpdateFailed("No data received from API")
            
            # Validate API response structure
            if not isinstance(data, dict):
                _LOGGER.error("Invalid API response format: expected dict, got %s", type(data))
                raise UpdateFailed("Invalid API response format")
            
            # Check for required top-level fields
            required_fields = ["timestamp", "query", "stops"]
            missing_fields = [field for field in required_fields if field not in data]
            if missing_fields:
                _LOGGER.error("Missing required fields in API response: %s", missing_fields)
                raise UpdateFailed(f"Invalid API response: missing fields {missing_fields}")
            
            _LOGGER.debug("API response keys: %s", list(data.keys()))
            
            # Check if we have the expected data structure at the top level
            if sensor_type == SENSOR_TYPE_ARRIVAL and "arrivals" in data:
                _LOGGER.debug("Found %d arrivals", len(data["arrivals"]))
            elif sensor_type == SENSOR_TYPE_DEPARTURE and "departures" in data:
                _LOGGER.debug("Found %d departures", len(data["departures"]))
            else:
                _LOGGER.warning("No departure/arrival data at top level: %s", list(data.keys()))
            # Mark successful update time (UTC ISO8601 without microseconds)
            from datetime import datetime, timezone
            self.last_successful_update = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            return data
            
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
