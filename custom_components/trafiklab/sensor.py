"""Sensor platform for Trafiklab integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    CONF_SENSOR_TYPE,
    CONF_DIRECTION,
    CONF_LINE_FILTER,
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
    description = (
        SENSOR_DESCRIPTIONS[1]
        if sensor_type == SENSOR_TYPE_ARRIVAL
        else SENSOR_DESCRIPTIONS[0]
    )
    async_add_entities([TrafikLabSensor(coordinator, entry, description)], True)


class TrafikLabSensor(CoordinatorEntity[TrafikLabCoordinator], SensorEntity):
    """Representation of a Trafiklab sensor."""

    def __init__(
        self,
        coordinator: TrafikLabCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_has_entity_name = True

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME),
            "manufacturer": "Trafiklab",
            "model": "Public Transport",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        items = self._get_data_items()
        if not items:
            return None
        first_item = items[0]
        scheduled_time = first_item.get("scheduled", "")
        realtime_time = first_item.get("realtime", "")
        departure_time = realtime_time or scheduled_time
        if not departure_time:
            return None
        try:
            from datetime import datetime

            dt = datetime.fromisoformat(departure_time)
            now = datetime.now()
            return int((dt - now).total_seconds() / 60)
        except Exception as err:  # pragma: no cover
            _LOGGER.debug("Time parse error: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        items = self._get_data_items()
        if not items:
            return {}
        first_item = items[0]
        merged_cfg = {**self._entry.data, **self._entry.options}
        configured_direction = merged_cfg.get(CONF_DIRECTION, "")
        return {
            "line": first_item.get("route", {}).get("designation", ""),
            "destination": first_item.get("route", {}).get("direction", ""),
            "direction": configured_direction,
            "scheduled_time": first_item.get("scheduled", ""),
            "expected_time": first_item.get("realtime", ""),
            "transport_mode": first_item.get("route", {}).get("transport_mode", ""),
            "real_time": first_item.get("is_realtime", False),
            "delay": first_item.get("delay", 0),
            "canceled": first_item.get("canceled", False),
            "platform": first_item.get("realtime_platform", {}).get("designation", ""),
            "upcoming": self._build_upcoming_array(items[:10], configured_direction),
            "attribution": "Data from Trafiklab.se",
            "last_update": getattr(self.coordinator, "last_successful_update", None),
        }

    def _build_upcoming_array(
        self, items: list[dict], configured_direction: str
    ) -> list[dict]:
        from datetime import datetime

        upcoming: list[dict] = []
        for idx, item in enumerate(items):
            scheduled_time = item.get("scheduled", "")
            realtime_time = item.get("realtime", "")
            departure_time = realtime_time or scheduled_time
            minutes_until = None
            time_formatted = ""
            if departure_time:
                try:
                    dt = datetime.fromisoformat(departure_time)
                    now = datetime.now()
                    minutes_until = int((dt - now).total_seconds() / 60)
                    time_formatted = dt.strftime("%H:%M")
                except Exception:  # pragma: no cover
                    pass
            upcoming.append(
                {
                    "index": idx,
                    "line": item.get("route", {}).get("designation", "") or "Unknown",
                    "destination": item.get("route", {}).get("direction", "")
                    or "Unknown",
                    "direction": configured_direction,
                    "scheduled_time": scheduled_time,
                    "expected_time": realtime_time,
                    "time_formatted": time_formatted,
                    "minutes_until": minutes_until,
                    "transport_mode": item.get("route", {}).get("transport_mode", "")
                    or "Unknown",
                    "real_time": bool(item.get("is_realtime", False)),
                    "delay": int(item.get("delay", 0)),
                    "delay_minutes": int(item.get("delay", 0) / 60)
                    if item.get("delay")
                    else 0,
                    "canceled": bool(item.get("canceled", False)),
                    "platform": item.get("realtime_platform", {})
                    .get("designation", "")
                    or item.get("scheduled_platform", {})
                    .get("designation", ""),
                    "route_name": item.get("route", {}).get("name", "") or "",
                    "agency": item.get("agency", {}).get("name", "") or "",
                    "trip_id": item.get("trip", {}).get("trip_id", "") or "",
                }
            )
        return upcoming

    def _get_data_items(self) -> list[dict]:
        data = self.coordinator.data
        if not data:
            return []
        raw_items: list[dict] = []
        if self.entity_description.key == "next_arrival":
            if isinstance(data.get("arrivals"), list):
                raw_items = data["arrivals"]
        else:
            if isinstance(data.get("departures"), list):
                raw_items = data["departures"]
        if not raw_items:
            return []
        merged_cfg = {**self._entry.data, **self._entry.options}
        line_filter = (merged_cfg.get(CONF_LINE_FILTER) or "").strip()
        direction_filter = (merged_cfg.get(CONF_DIRECTION) or "").strip().lower()
        line_set = (
            {ln.strip() for ln in line_filter.split(",") if ln.strip()}
            if line_filter
            else None
        )

        def match_line(item: dict) -> bool:
            if not line_set:
                return True
            designation = item.get("route", {}).get("designation", "")
            return designation in line_set

        def match_direction(item: dict) -> bool:
            if not direction_filter:
                return True
            destination = item.get("route", {}).get("direction", "")
            return direction_filter in destination.lower()

        filtered = [it for it in raw_items if match_line(it) and match_direction(it)]
        _LOGGER.debug(
            "Filtered %d -> %d items (lines=%s direction_substr='%s')",
            len(raw_items),
            len(filtered),
            line_filter or "*",
            direction_filter or "*",
        )
        return filtered
