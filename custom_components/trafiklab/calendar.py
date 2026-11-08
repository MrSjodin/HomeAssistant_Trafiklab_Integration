"""Calendar platform for Trafiklab.

Exposes the departures, arrivals or Resrobot trips that the coordinator has
already fetched as calendar events, which are easier to show on a dashboard
than the sensor's attribute arrays. The entity is disabled by default; enable
it from the entity settings to use it.

The calendar only knows what the coordinator holds, i.e. the configured time
window ahead. Past events and events outside the window are not available.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DIRECTION,
    CONF_LINE_FILTER,
    CONF_MAX_TRIP_DURATION,
    CONF_SENSOR_TYPE,
    CONF_TRANSPORT_MODES,
    DOMAIN,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_RESROBOT,
)
from .coordinator import TrafikLabCoordinator
from .sensor import filter_realtime_items, normalize_resrobot_trips

_LOGGER = logging.getLogger(__name__)

# Trafiklab and Resrobot report Swedish local time without a UTC offset
API_TIME_ZONE = ZoneInfo("Europe/Stockholm")

# Departures and arrivals are points in time; give them a short duration so
# they render as events
POINT_EVENT_DURATION = timedelta(minutes=1)

_TEXT = {
    "en": {
        "canceled": "Canceled",
        "platform": "Platform",
        "scheduled": "Scheduled",
        "expected": "Expected",
        "delay": "Delay",
        "minutes": "min",
        "realtime": "Realtime",
        "timetable": "Timetable",
        "operator": "Operator",
    },
    "sv": {
        "canceled": "Inställd",
        "platform": "Läge",
        "scheduled": "Tidtabell",
        "expected": "Beräknad",
        "delay": "Försening",
        "minutes": "min",
        "realtime": "Realtid",
        "timetable": "Enligt tidtabell",
        "operator": "Operatör",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Trafiklab calendar for this config entry."""
    coordinator: TrafikLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TrafikLabCalendar(coordinator, entry)])


def parse_api_time(value: Any) -> datetime | None:
    """Parse a Trafiklab/Resrobot time string into an aware datetime."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip().replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=API_TIME_ZONE)
    return parsed


class TrafikLabCalendar(CoordinatorEntity[TrafikLabCoordinator], CalendarEntity):
    """Calendar with the departures, arrivals or trips of a Trafiklab entry."""

    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: TrafikLabCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DEPARTURE)
        self._attr_unique_id = f"{entry.entry_id}_calendar"
        if self._sensor_type == SENSOR_TYPE_RESROBOT:
            self._attr_translation_key = "trips"
            self._attr_icon = "mdi:train-bus"
        elif self._sensor_type == SENSOR_TYPE_ARRIVAL:
            self._attr_translation_key = "arrivals"
            self._attr_icon = "mdi:bus-clock"
        else:
            self._attr_translation_key = "departures"
            self._attr_icon = "mdi:bus-clock"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info identical to the sensor so the calendar joins the same device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME),
            "manufacturer": "Trafiklab",
            "model": "Public Transport",
        }

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next event."""
        now = dt_util.now()
        for event in self._build_events():
            if event.end > now:
                return event
        return None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events overlapping the requested range."""
        return [
            event
            for event in self._build_events()
            if event.start < end_date and event.end > start_date
        ]

    # ------------------------------------------------------------------
    # Event building
    # ------------------------------------------------------------------
    def _text(self, key: str) -> str:
        language = (self.hass.config.language or "en").split("-")[0] if self.hass else "en"
        return _TEXT.get(language, _TEXT["en"])[key]

    def _build_events(self) -> list[CalendarEvent]:
        data = self.coordinator.data
        if not data:
            return []
        try:
            if self._sensor_type == SENSOR_TYPE_RESROBOT:
                events = self._build_trip_events(data)
            else:
                events = self._build_stop_events(data)
        except Exception:  # pragma: no cover - never break the calendar on odd data
            _LOGGER.exception("Failed to build calendar events for %s", self.entity_id)
            return []
        events.sort(key=lambda event: event.start)
        return events

    def _build_stop_events(self, data: dict) -> list[CalendarEvent]:
        key = "arrivals" if self._sensor_type == SENSOR_TYPE_ARRIVAL else "departures"
        raw_items = data.get(key)
        if not isinstance(raw_items, list):
            return []
        cfg = {**self._entry.data, **self._entry.options}
        items = filter_realtime_items(
            raw_items,
            cfg.get(CONF_LINE_FILTER) or "",
            cfg.get(CONF_DIRECTION) or "",
            cfg.get(CONF_TRANSPORT_MODES) or [],
        )

        events: list[CalendarEvent] = []
        for item in items:
            scheduled = parse_api_time(item.get("scheduled"))
            expected = parse_api_time(item.get("realtime")) or scheduled
            if expected is None:
                continue
            route = item.get("route") or {}
            line = route.get("designation") or ""
            destination = route.get("direction") or ""
            canceled = bool(item.get("canceled"))
            platform = (item.get("realtime_platform") or {}).get("designation") or (
                item.get("scheduled_platform") or {}
            ).get("designation") or ""

            summary = " ".join(part for part in (line, destination) if part) or "?"
            if canceled:
                summary = f"{self._text('canceled')}: {summary}"

            lines: list[str] = []
            if platform:
                lines.append(f"{self._text('platform')}: {platform}")
            if scheduled is not None:
                lines.append(f"{self._text('scheduled')}: {scheduled:%H:%M}")
            if expected != scheduled:
                lines.append(f"{self._text('expected')}: {expected:%H:%M}")
            delay_minutes = int((item.get("delay") or 0) / 60)
            if delay_minutes:
                lines.append(f"{self._text('delay')}: {delay_minutes} {self._text('minutes')}")
            lines.append(
                self._text("realtime") if item.get("is_realtime") else self._text("timetable")
            )
            agency = (item.get("agency") or {}).get("name")
            if agency:
                lines.append(f"{self._text('operator')}: {agency}")

            trip = item.get("trip") or {}
            uid = None
            if trip.get("trip_id"):
                uid = f"{trip.get('trip_id')}_{trip.get('start_date', '')}"

            events.append(
                CalendarEvent(
                    start=expected,
                    end=expected + POINT_EVENT_DURATION,
                    summary=summary,
                    description="\n".join(lines),
                    location=(item.get("stop") or {}).get("name") or None,
                    uid=uid,
                )
            )
        return events

    def _build_trip_events(self, data: dict) -> list[CalendarEvent]:
        cfg = {**self._entry.data, **self._entry.options}
        trips = normalize_resrobot_trips(
            data.get("Trip", []), cfg.get(CONF_MAX_TRIP_DURATION)
        )

        events: list[CalendarEvent] = []
        for trip in trips:
            legs = trip.get("legs") or []
            if not legs:
                continue
            first, last = legs[0], legs[-1]
            start = parse_api_time(first.get("expected_time")) or parse_api_time(
                first.get("origin_time")
            )
            end = parse_api_time(last.get("dest_time"))
            if start is None:
                continue
            if end is None or end <= start:
                end = start + POINT_EVENT_DURATION

            canceled = any(leg.get("canceled") for leg in legs)
            summary = f"{first.get('origin_name', '')} → {last.get('dest_name', '')}"
            if canceled:
                summary = f"{self._text('canceled')}: {summary}"

            lines: list[str] = []
            for leg in legs:
                leg_start = parse_api_time(leg.get("expected_time")) or parse_api_time(
                    leg.get("origin_time")
                )
                time_text = f"{leg_start:%H:%M}" if leg_start else ""
                product = str(leg.get("product") or leg.get("type") or "")
                route = f"{leg.get('origin_name', '')} → {leg.get('dest_name', '')}"
                parts = [p for p in (time_text, product, route) if p]
                if leg.get("platform"):
                    parts.append(f"({self._text('platform')} {leg['platform']})")
                if leg.get("canceled"):
                    parts.append(f"[{self._text('canceled')}]")
                lines.append(" ".join(parts))

            events.append(
                CalendarEvent(
                    start=start,
                    end=end,
                    summary=summary,
                    description="\n".join(lines),
                    location=first.get("origin_name") or None,
                    uid=f"{self._entry.entry_id}_{start.isoformat()}_{end.isoformat()}",
                )
            )
        return events
