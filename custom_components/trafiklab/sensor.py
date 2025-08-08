"""Sensor platform for Trafiklab integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SENSOR_TYPE,
    CONF_LINE_FILTER,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_ARRIVAL,
    ATTR_STOP_NAME,
    ATTR_LINE,
    ATTR_DESTINATION,
    ATTR_DIRECTION,
    ATTR_EXPECTED_TIME,
    ATTR_REAL_TIME,
    ATTR_TRANSPORT_MODE,
    ATTR_DEVIATIONS,
)
from .coordinator import TrafikLabCoordinator
from .translation_helper import translate_sensor_name, translate_state, translate_device_info

_LOGGER = logging.getLogger(__name__)


def get_sensor_descriptions() -> list[SensorEntityDescription]:
    """Get sensor descriptions with translated names."""
    return [
        SensorEntityDescription(
            key="next_departure",
            name=translate_sensor_name("next_departure"),
            icon="mdi:bus-clock",
        ),
        SensorEntityDescription(
            key="next_arrival", 
            name=translate_sensor_name("next_arrival"),
            icon="mdi:bus-stop",
        ),
        SensorEntityDescription(
            key="departures",
            name=translate_sensor_name("departures"),
            icon="mdi:timetable",
        ),
        SensorEntityDescription(
            key="arrivals",
            name=translate_sensor_name("arrivals"), 
            icon="mdi:bus-stop-covered",
        ),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Trafiklab sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Determine which sensors to create based on sensor type
    sensor_type = entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DEPARTURE)
    
    entities = []
    sensor_descriptions = get_sensor_descriptions()
    
    if sensor_type == SENSOR_TYPE_DEPARTURE:
        # Create departure sensors
        for description in sensor_descriptions:
            if description.key in ["next_departure", "departures"]:
                entities.append(TrafikLabSensor(coordinator, entry, description))
    else:  # SENSOR_TYPE_ARRIVAL
        # Create arrival sensors
        for description in sensor_descriptions:
            if description.key in ["next_arrival", "arrivals"]:
                entities.append(TrafikLabSensor(coordinator, entry, description))
    
    async_add_entities(entities)


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
        self._attr_name = f"{entry.data.get(CONF_NAME)} {description.name}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME),
            "manufacturer": translate_device_info("manufacturer"),
            "model": translate_device_info("model"),
            "entry_type": "service",
        }

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not self.coordinator.data:
            return None

        if self.entity_description.key in ["next_departure", "next_arrival"]:
            return self._get_next_departure_state()
        elif self.entity_description.key in ["departures", "arrivals"]:
            return self._get_departures_count()

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        attrs = {
            ATTR_STOP_NAME: self.coordinator.data.get("stop_name", ""),
            "sensor_type": self.coordinator.sensor_type,
            "last_updated": self.coordinator.data.get("last_updated"),
        }

        # Add line filter info if configured
        if self.coordinator.line_filter:
            attrs["line_filter"] = self.coordinator.line_filter

        # Add configured direction filter as main "direction" attribute
        if self.coordinator.direction:
            attrs["direction"] = self.coordinator.direction
        else:
            attrs["direction"] = "2"  # Both directions when no filter is set

        # Add time window info
        attrs["time_window"] = self.coordinator.time_window
        
        # Add refresh interval info
        attrs["refresh_interval"] = self.coordinator.refresh_interval

        if self.entity_description.key in ["next_departure", "next_arrival"]:
            attrs.update(self._get_next_departure_attributes())
        elif self.entity_description.key in ["departures", "arrivals"]:
            attrs.update(self._get_departures_attributes())

        return attrs

    def _get_next_departure_state(self) -> str | None:
        """Get the state for next departure sensor."""
        departures = self.coordinator.data.get("departures", [])
        if not departures:
            if self.entity_description.key == "next_departure":
                return translate_state("no_departures")
            else:
                return translate_state("no_arrivals")

        next_departure = departures[0]
        display_time = next_departure.get("display_time", "")
        
        if display_time:
            return display_time
        
        expected_time = next_departure.get("expected_time", "")
        if expected_time:
            return expected_time
            
        return translate_state("unknown")

    def _get_next_departure_attributes(self) -> dict[str, Any]:
        """Get attributes for next departure sensor."""
        departures = self.coordinator.data.get("departures", [])
        if not departures:
            return {}

        next_departure = departures[0]
        return {
            ATTR_LINE: next_departure.get("line", ""),
            ATTR_DESTINATION: next_departure.get("destination", ""),
            "route_direction": next_departure.get("direction", ""),  # API direction for this specific departure
            ATTR_EXPECTED_TIME: next_departure.get("expected_time", ""),
            ATTR_REAL_TIME: next_departure.get("real_time", False),
            ATTR_TRANSPORT_MODE: next_departure.get("transport_mode", ""),
            ATTR_DEVIATIONS: next_departure.get("deviations", []),
            "scheduled_time": next_departure.get("scheduled_time", ""),
        }

    def _get_departures_count(self) -> int:
        """Get the count of departures."""
        departures = self.coordinator.data.get("departures", [])
        return len(departures)

    def _get_departures_attributes(self) -> dict[str, Any]:
        """Get attributes for departures sensor."""
        departures = self.coordinator.data.get("departures", [])
        
        # Limit to next 10 departures to avoid too much data
        limited_departures = departures[:10]
        
        # Create array of upcoming departures/arrivals
        upcoming_items = []
        for departure in limited_departures:
            item = {
                "line": departure.get("line", ""),
                "destination": departure.get("destination", ""),
                "route_direction": departure.get("direction", ""),  # API direction for this specific departure
                "time": departure.get("display_time") or departure.get("expected_time", ""),
                "scheduled_time": departure.get("scheduled_time", ""),
                "expected_time": departure.get("expected_time", ""),
                "transport_mode": departure.get("transport_mode", ""),
                "real_time": departure.get("real_time", False),
                "deviations": departure.get("deviations", [])
            }
            upcoming_items.append(item)
        
        # Determine the attribute name based on sensor type
        if self.entity_description.key == "departures":
            attr_name = "upcoming_departures"
        else:  # arrivals
            attr_name = "upcoming_arrivals"
        
        return {attr_name: upcoming_items}
