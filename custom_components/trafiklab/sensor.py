"""Sensor platform for Trafiklab integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SENSOR_TYPE,
    CONF_DIRECTION,
    SENSOR_TYPE_ARRIVAL,
)
from .coordinator import TrafikLabCoordinator

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="next_departure",
        translation_key="next_departure",
        icon="mdi:bus-clock",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
    SensorEntityDescription(
        key="next_arrival", 
        translation_key="next_arrival",
        icon="mdi:bus-stop",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trafiklab sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensor_type = entry.data.get(CONF_SENSOR_TYPE, "departures")
    
    # Create appropriate sensor based on type
    if sensor_type == SENSOR_TYPE_ARRIVAL:
        description = SENSOR_DESCRIPTIONS[1]  # next_arrival
    else:
        description = SENSOR_DESCRIPTIONS[0]  # next_departure
    
    entities = [TrafikLabSensor(coordinator, entry, description)]
    async_add_entities(entities, True)


class TrafikLabSensor(CoordinatorEntity[TrafikLabCoordinator], SensorEntity):
    """Representation of a Trafiklab sensor."""

    def __init__(
        self,
        coordinator: TrafikLabCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME),
            "manufacturer": "Trafiklab",
            "model": "Public Transport",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        # Get first item from API data
        items = self._get_data_items()
        if not items:
            return None

        # Get the next departure/arrival time
        first_item = items[0]
        
        # Handle new Trafiklab Realtime API format
        scheduled_time = first_item.get("scheduled", "")
        realtime_time = first_item.get("realtime", "")
        
        # Use realtime if available, otherwise scheduled
        departure_time = realtime_time if realtime_time else scheduled_time
        
        if departure_time:
            try:
                from datetime import datetime
                # API returns format: "2025-04-01T14:30:00"
                dt = datetime.fromisoformat(departure_time)
                now = datetime.now()
                
                # Calculate minutes until departure/arrival
                minutes = int((dt - now).total_seconds() / 60)
                
                # Return minutes (can be negative if departure has passed)
                return minutes
            except Exception as e:
                _LOGGER.warning("Error calculating minutes until departure: %s", e)
                return None
                
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        items = self._get_data_items()
        if not items:
            return {}

        first_item = items[0]
        
        # Get the configured direction filter from the entry
        configured_direction = self._entry.data.get(CONF_DIRECTION, "")
        
        return {
            "line": first_item.get("route", {}).get("designation", ""),
            "destination": first_item.get("route", {}).get("direction", ""),
            "direction": configured_direction,  # The user-configured direction filter
            "scheduled_time": first_item.get("scheduled", ""),
            "expected_time": first_item.get("realtime", ""),
            "transport_mode": first_item.get("route", {}).get("transport_mode", ""),
            "real_time": first_item.get("is_realtime", False),
            "delay": first_item.get("delay", 0),
            "canceled": first_item.get("canceled", False),
            "platform": first_item.get("realtime_platform", {}).get("designation", ""),
            "upcoming": self._build_upcoming_array(items[:10], configured_direction),  # Up to 10 items
        }

    def _build_upcoming_array(self, items: list[dict], configured_direction: str) -> list[dict]:
        """Build a well-structured upcoming array for automation use."""
        from datetime import datetime
        
        upcoming = []
        
        for idx, item in enumerate(items):
            # Extract time information
            scheduled_time = item.get("scheduled", "")
            realtime_time = item.get("realtime", "")
            departure_time = realtime_time if realtime_time else scheduled_time
            
            # Calculate minutes until departure
            minutes_until = None
            time_formatted = ""
            
            if departure_time:
                try:
                    dt = datetime.fromisoformat(departure_time)
                    now = datetime.now()
                    minutes_until = int((dt - now).total_seconds() / 60)
                    time_formatted = dt.strftime("%H:%M")  # Format as HH:MM
                except Exception as e:
                    _LOGGER.debug("Error parsing time for upcoming item %d: %s", idx, e)
            
            # Build automation-friendly item
            upcoming_item = {
                "index": idx,  # Position in the list (0-based)
                "line": item.get("route", {}).get("designation", "") or "Unknown",
                "destination": item.get("route", {}).get("direction", "") or "Unknown",
                "direction": configured_direction,
                "scheduled_time": scheduled_time,
                "expected_time": realtime_time,
                "time_formatted": time_formatted,  # Human-readable time (HH:MM)
                "minutes_until": minutes_until,  # Integer minutes until departure
                "transport_mode": item.get("route", {}).get("transport_mode", "") or "Unknown",
                "real_time": bool(item.get("is_realtime", False)),
                "delay": int(item.get("delay", 0)),  # Ensure it's an integer
                "delay_minutes": int(item.get("delay", 0) / 60) if item.get("delay") else 0,  # Convert seconds to minutes
                "canceled": bool(item.get("canceled", False)),
                "platform": item.get("realtime_platform", {}).get("designation", "") or item.get("scheduled_platform", {}).get("designation", ""),
                "route_name": item.get("route", {}).get("name", "") or "",
                "agency": item.get("agency", {}).get("name", "") or "",
                "trip_id": item.get("trip", {}).get("trip_id", "") or "",
            }
            
            upcoming.append(upcoming_item)
        
        return upcoming

    def _get_data_items(self) -> list[dict]:
        """Get data items from coordinator based on sensor type."""
        data = self.coordinator.data
        if not data:
            _LOGGER.debug("No data from coordinator")
            return []

        _LOGGER.debug("Coordinator data keys: %s", list(data.keys()))
        
        # Handle Trafiklab Realtime API response structure
        if self.entity_description.key == "next_arrival":
            # Look for arrivals in response
            if "arrivals" in data:
                _LOGGER.debug("Found %d arrivals", len(data["arrivals"]))
                return data["arrivals"]
        else:
            # Look for departures in response  
            if "departures" in data:
                _LOGGER.debug("Found %d departures", len(data["departures"]))
                return data["departures"]
        
        _LOGGER.warning("No relevant data found for sensor type: %s", self.entity_description.key)
        return []
