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
        
        refresh_interval = entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)
        
        super().__init__(
            hass,
            _LOGGER,
            name="Trafiklab",
            update_interval=timedelta(seconds=refresh_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Trafiklab API."""
        try:
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
            
            _LOGGER.debug("API response keys: %s", list(data.keys()))
            
            # Check if we have the expected data structure
            if sensor_type == SENSOR_TYPE_ARRIVAL and "arrivals" in data:
                _LOGGER.debug("Found %d arrivals", len(data["arrivals"]))
            elif "departures" in data:
                _LOGGER.debug("Found %d departures", len(data["departures"]))
            else:
                _LOGGER.warning("Unexpected API response structure: %s", list(data.keys()))
                
            return data
            
        except Exception as err:
            _LOGGER.error("Error communicating with API: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
