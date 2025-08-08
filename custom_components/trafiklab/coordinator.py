"""Data update coordinator for Trafiklab."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_SENSOR_TYPE,
    CONF_LINE_FILTER,
    CONF_DIRECTION,
    CONF_TIME_WINDOW,
    CONF_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_WINDOW,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_ARRIVAL,
)
from .api import TrafikLabApiClient, TrafikLabApiError
from .translation_helper import translate_state

_LOGGER = logging.getLogger(__name__)


class TrafikLabCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Trafiklab."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.api_key = entry.data[CONF_API_KEY]
        self.stop_id = entry.data[CONF_STOP_ID]
        self.sensor_type = entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DEPARTURE)
        self.line_filter = entry.data.get(CONF_LINE_FILTER, "")
        self.direction = entry.data.get(CONF_DIRECTION, "")
        self.time_window = entry.data.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)
        self.refresh_interval = entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.entry = entry

        _LOGGER.debug(
            "Initializing coordinator with refresh interval: %d seconds", 
            self.refresh_interval
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=self.refresh_interval),
        )

    async def async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle updated config entry."""
        old_refresh_interval = self.refresh_interval
        
        # Update configuration values
        self.api_key = entry.data[CONF_API_KEY]
        self.stop_id = entry.data[CONF_STOP_ID]
        self.sensor_type = entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DEPARTURE)
        self.line_filter = entry.data.get(CONF_LINE_FILTER, "")
        self.direction = entry.data.get(CONF_DIRECTION, "")
        self.time_window = entry.data.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)
        self.refresh_interval = entry.data.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)
        self.entry = entry
        
        # Update refresh interval if it changed
        if old_refresh_interval != self.refresh_interval:
            _LOGGER.debug(
                "Refresh interval changed from %d to %d seconds", 
                old_refresh_interval, 
                self.refresh_interval
            )
            self.update_interval = timedelta(seconds=self.refresh_interval)
            # Trigger immediate refresh with new interval
            await self.async_refresh()

    async def async_request_refresh_now(self) -> None:
        """Request an immediate refresh."""
        _LOGGER.debug("Manual refresh requested")
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from Trafiklab API."""
        _LOGGER.debug("Updating data from Trafiklab API (refresh interval: %d seconds)", self.refresh_interval)
        
        try:
            async with TrafikLabApiClient(self.api_key) as client:
                # Get data based on sensor type
                if self.sensor_type == SENSOR_TYPE_ARRIVAL:
                    _LOGGER.debug("Fetching arrivals for stop: %s", self.stop_id)
                    result = await client.get_arrivals(self.stop_id)
                else:
                    _LOGGER.debug("Fetching departures for stop: %s", self.stop_id)
                    result = await client.get_departures(self.stop_id)

                _LOGGER.debug("API response received: %s", result)
                
                # Process the response
                processed_data = self._process_api_data(result)
                _LOGGER.debug("Successfully updated data at %s", processed_data.get("last_updated"))
                return processed_data

        except TrafikLabApiError as err:
            _LOGGER.error("Trafiklab API error: %s", err)
            raise UpdateFailed(f"Trafiklab API error: {err}") from err
        except Exception as err:
            _LOGGER.error("Unexpected error: %s", err)
            raise UpdateFailed(f"Unexpected error: {err}") from err

    def _process_api_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Process the API data from the new Trafiklab Realtime API."""
        current_time = datetime.now()
        processed_data = {
            "departures": [],
            "stop_name": "",
            "last_updated": current_time,
        }

        _LOGGER.debug("Processing API data at %s", current_time.isoformat())
        _LOGGER.debug("Raw API data structure: %s", list(data.keys()) if isinstance(data, dict) else type(data))

        # Handle different possible API response structures
        if not isinstance(data, dict):
            _LOGGER.warning("API response is not a dictionary: %s", type(data))
            return processed_data

        # Check for different possible response structures
        departures_data = []
        stop_name = ""

        # Try different possible keys for the response
        if "departures" in data:
            departures_data = data["departures"]
            _LOGGER.debug("Found departures data with %d items", len(departures_data))
        elif "arrivals" in data:
            departures_data = data["arrivals"]
            _LOGGER.debug("Found arrivals data with %d items", len(departures_data))
        elif "stops" in data:
            # Handle nested structure with stops
            _LOGGER.debug("Found stops structure")
            if data["stops"]:
                stop_info = data["stops"][0]
                stop_name = stop_info.get("name", "")
                
                # Look for departures/arrivals in the stop data
                data_key = "arrivals" if self.sensor_type == SENSOR_TYPE_ARRIVAL else "departures"
                if data_key in stop_info:
                    departures_data = stop_info[data_key]
                    _LOGGER.debug("Found %s data in stop with %d items", data_key, len(departures_data))
        else:
            _LOGGER.warning("Unknown API response structure. Keys: %s", list(data.keys()))
            return processed_data

        processed_data["stop_name"] = stop_name

        # Process each departure/arrival item
        for item in departures_data:
            processed_item = self._process_api_item(item)
            if processed_item:
                # Apply line filter if specified
                if self.line_filter:
                    allowed_lines = [line.strip() for line in self.line_filter.split(",")]
                    line_designation = processed_item.get("line", "")
                    if line_designation not in allowed_lines:
                        continue
                
                # Apply direction filter if specified
                if self.direction:
                    # This is a simple direction filter - might need refinement based on actual data
                    route_direction = processed_item.get("direction", "")
                    if self.direction == "0" and "1" not in route_direction:
                        continue
                    elif self.direction == "1" and "2" not in route_direction:
                        continue
                
                processed_data["departures"].append(processed_item)
                processed_data["departures"].append(processed_item)

        # Sort by scheduled/realtime time
        processed_data["departures"].sort(key=lambda x: x.get("scheduled_datetime", datetime.max))
        
        _LOGGER.debug("Processed %d items successfully", len(processed_data["departures"]))
        return processed_data

    def _process_api_item(self, item: dict[str, Any]) -> dict[str, Any] | None:
        """Process a single departure/arrival item from the API."""
        try:
            _LOGGER.debug("Processing API item: %s", list(item.keys()) if isinstance(item, dict) else type(item))
            
            # Handle different possible API structures
            if not isinstance(item, dict):
                _LOGGER.warning("API item is not a dictionary: %s", type(item))
                return None
            
            # Extract route information - try different possible structures
            route = item.get("route", {})
            if not route and "line" in item:
                # Alternative structure where line info is directly in item
                route = {
                    "designation": item.get("line", ""),
                    "destination": {"name": item.get("destination", "")},
                    "direction": item.get("direction", ""),
                    "transport_mode": item.get("transport_mode", ""),
                }
            
            # Extract times - try different possible field names
            expected_time = (
                item.get("realtime", "") or 
                item.get("expected_time", "") or 
                item.get("time", "")
            )
            
            scheduled_time = (
                item.get("scheduled", "") or 
                item.get("scheduled_time", "") or 
                item.get("timetabled_time", "")
            )
            
            return {
                "line": route.get("designation", "") or item.get("line", ""),
                "destination": (
                    route.get("destination", {}).get("name", "") or 
                    item.get("destination", "")
                ),
                "direction": route.get("direction", "") or item.get("direction", ""),
                "expected_time": expected_time,
                "scheduled_time": scheduled_time,
                "display_time": self._format_display_time(expected_time),
                "transport_mode": (
                    route.get("transport_mode", "").lower() or 
                    item.get("transport_mode", "").lower()
                ),
                "real_time": item.get("is_realtime", False) or item.get("real_time", False),
                "delay": item.get("delay", 0),
                "canceled": item.get("canceled", False),
                "deviations": item.get("alerts", []) or item.get("deviations", []),
                "scheduled_datetime": self._parse_new_datetime(scheduled_time),
                "realtime_datetime": self._parse_new_datetime(expected_time),
                "agency": item.get("agency", {}).get("name", "") or item.get("operator", ""),
                "platform": (
                    item.get("realtime_platform", {}).get("designation", "") or
                    item.get("platform", "")
                ),
            }
        except Exception as err:
            _LOGGER.warning("Error processing API item: %s. Item data: %s", err, item)
            return None

    def _format_display_time(self, time_str: str) -> str:
        """Format time for display."""
        if not time_str:
            return ""
            
        try:
            # Parse the datetime from API format: "2025-04-01T14:30:00"
            dt = datetime.fromisoformat(time_str)
            now = datetime.now()
            
            # Calculate minutes until departure/arrival
            minutes = int((dt - now).total_seconds() / 60)
            
            if minutes <= 0:
                return translate_state("now")
            elif minutes == 1:
                return translate_state("one_minute")
            else:
                return translate_state("minutes", minutes=minutes)
        except Exception:
            return time_str[-5:]  # Return just the time part HH:MM

    def _parse_new_datetime(self, datetime_str: str | None) -> datetime | None:
        """Parse datetime string from new API format."""
        if not datetime_str:
            return None
        
        try:
            # New API returns datetime in ISO format: "2025-04-01T14:30:00"
            return datetime.fromisoformat(datetime_str)
        except Exception as err:
            _LOGGER.warning("Error parsing datetime %s: %s", datetime_str, err)
            return None
