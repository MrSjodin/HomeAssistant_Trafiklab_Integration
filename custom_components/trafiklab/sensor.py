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
from homeassistant.helpers import entity_registry as er

from .const import (
    DOMAIN,
    CONF_SENSOR_TYPE,
    CONF_DIRECTION,
    CONF_LINE_FILTER,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_RESROBOT,
)
from .coordinator import TrafikLabCoordinator

_LOGGER = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    """Simple slugify helper for entity_id parts: lowercase, underscores, safe chars only."""
    import re
    v = (value or "").strip().lower()
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^a-z0-9_]", "_", v)
    v = re.sub(r"_+", "_", v)
    return v.strip("_") or "trafiklab"

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
    sensor_type = entry.data.get(CONF_SENSOR_TYPE, "departure")
    if sensor_type == SENSOR_TYPE_RESROBOT:
        description = SensorEntityDescription(
            key="resrobot_travel",
            translation_key="resrobot_travel",
            icon="mdi:train-car",
            device_class=SensorDeviceClass.DURATION,
            native_unit_of_measurement=UnitOfTime.MINUTES,
        )
    elif sensor_type == SENSOR_TYPE_ARRIVAL:
        description = SENSOR_DESCRIPTIONS[1]
    else:
        description = SENSOR_DESCRIPTIONS[0]
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
        self._attr_has_entity_name = False
        configured_name = (self._entry.data.get(CONF_NAME) or "").strip() or "trafiklab"
        name_slug = _slugify(configured_name)
        stype = self._entry.data.get(CONF_SENSOR_TYPE, "departure")
        if stype == SENSOR_TYPE_ARRIVAL:
            suggested = f"trafiklab_arrivals_{name_slug}"
        elif stype == SENSOR_TYPE_RESROBOT:
            suggested = f"trafiklab_travel_{name_slug}"
        else:
            suggested = f"trafiklab_departures_{name_slug}"
        self._attr_suggested_object_id = suggested

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME),
            "manufacturer": "Trafiklab",
            "model": "Public Transport"
        }

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data:
            return None
        sensor_type = self._entry.data.get(CONF_SENSOR_TYPE, "departure")
        if sensor_type == "resrobot_travel_search":
            # Parse Resrobot response and filter by time window
            trips_raw = self.coordinator.data.get("Trip", [])
            if not trips_raw:
                return None
            # Normalize + sort trips/legs locally as well (in case coordinator didn't)
            trips_sorted = self._normalize_resrobot_trips(trips_raw)
            options = {**self._entry.options, **self._entry.data}
            time_window = int(options.get("time_window", 60))
            from datetime import datetime
            now = datetime.now()
            # Find first leg within time window from sorted trips/legs
            for trip in trips_sorted:
                for leg in trip.get("legs", []):
                    origin_time = leg.get("origin_time", "")
                    if not origin_time:
                        continue
                    try:
                        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                            try:
                                dt = datetime.strptime(origin_time, fmt)
                                break
                            except ValueError:
                                dt = None
                        if not dt:
                            continue
                        minutes_until = int((dt - now).total_seconds() / 60)
                        if 0 <= minutes_until <= time_window:
                            return minutes_until
                    except Exception as err:
                        _LOGGER.debug("Resrobot time parse error: %s", err)
                        continue
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
            # Handle timezone-aware vs naive datetimes safely
            if dt.tzinfo is not None:
                now = datetime.now(dt.tzinfo)
            else:
                now = datetime.now()
            return int((dt - now).total_seconds() / 60)
        except Exception as err:  # pragma: no cover
            _LOGGER.debug("Time parse error: %s", err)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            return {}
        sensor_type = self._entry.data.get(CONF_SENSOR_TYPE, "departure")
        if sensor_type == "resrobot_travel_search":
            # Build a sorted top-level trips array and per-trip sorted legs array
            trips_raw = self.coordinator.data.get("Trip", [])
            if not trips_raw:
                return {}
            trips_sorted = self._normalize_resrobot_trips(trips_raw)
            return {
                "num_trips": len(trips_sorted),
                "trips": trips_sorted,
                "attribution": "Data from Resrobot/Trafiklab.se",
                "last_update": getattr(self.coordinator, "last_successful_update", None),
                "integration": DOMAIN,
            }
        # ...existing code for departure/arrival...
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
            "integration": DOMAIN,
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
                    if dt.tzinfo is not None:
                        now = datetime.now(dt.tzinfo)
                    else:
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

    def _normalize_resrobot_trips(self, trips_raw: Any) -> list[dict[str, Any]]:
        """Normalize and sort ResRobot trips and their legs for attribute exposure.

        Returns a list of trips where each has a key "legs" which is a list of
        simplified leg dicts, sorted by origin datetime. The trips list itself
        is sorted by the first leg's origin datetime.
        """
        from datetime import datetime

        # Ensure list at top level
        if isinstance(trips_raw, dict):
            trips_iter = [trips_raw]
        else:
            trips_iter = list(trips_raw or [])

        def parse_dt(date_str: str, time_str: str) -> datetime | None:
            if not date_str or not time_str:
                return None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(f"{date_str} {time_str}", fmt)
                except ValueError:
                    continue
            return None

        # Minimal fallback mapping; prefer Product-provided labels when available
        category_map = {
            "BLT": "Bus",
            "BUS": "Bus",
            "TRN": "Train",
            "REG": "Regional Train",
            "LDT": "Long-distance Train",
            "TRM": "Tram",
            "MET": "Metro",
            "SHP": "Ferry",
            "SHIP": "Ferry",
        }

        def translate_category(abbrev: str | None, product_obj: dict) -> str:
            # Prefer long/short labels from Product when present
            if product_obj:
                name_l = product_obj.get("catOutL") or product_obj.get("catInL")
                if name_l:
                    return str(name_l)
                name_s = product_obj.get("catOutS") or product_obj.get("catInS")
                if name_s:
                    return str(name_s)
            if abbrev and abbrev in category_map:
                return category_map[abbrev]
            return abbrev or ""

        def parse_iso_duration_minutes(dur: Any) -> int | None:
            """Parse ISO8601 duration (e.g., PT1H30M, PT9M, PT45S) into integer minutes."""
            if not isinstance(dur, str) or not dur:
                return None
            # Basic ISO8601 duration parser focusing on time part; supports days as well.
            import re
            # Split date and time components
            # Example: P1DT2H3M4S, PT45M, PT1H, PT30S
            pattern = re.compile(
                r"^P(?:(?P<weeks>\d+)W)?(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
                re.IGNORECASE,
            )
            m = pattern.match(dur)
            if not m:
                return None
            weeks = int(m.group("weeks") or 0)
            days = int(m.group("days") or 0)
            hours = int(m.group("hours") or 0)
            minutes = int(m.group("minutes") or 0)
            seconds = int(m.group("seconds") or 0)
            total_minutes = weeks * 7 * 24 * 60 + days * 24 * 60 + hours * 60 + minutes + (seconds // 60)
            return total_minutes

        trips_out: list[dict[str, Any]] = []
        for idx, trip in enumerate(trips_iter):
            leg_container = (trip or {}).get("LegList", {}) or {}
            legs = leg_container.get("Leg")
            if legs is None:
                legs_list = []
            elif isinstance(legs, dict):
                legs_list = [legs]
            else:
                legs_list = list(legs)

            simplified_legs: list[dict[str, Any]] = []
            for leg in legs_list:
                origin = (leg or {}).get("Origin", {}) or {}
                dest = (leg or {}).get("Destination", {}) or {}
                product = (leg or {}).get("Product", {})
                if isinstance(product, list):
                    product_obj = product[0] if product else {}
                else:
                    product_obj = product or {}
                # Determine translated category
                category_abbrev = (leg or {}).get("category") or product_obj.get("catOut") or product_obj.get("catIn")
                category_full = translate_category(category_abbrev, product_obj)
                # Determine duration in minutes (prefer leg.duration, fallback to GisRoute.durS)
                dur_iso = (leg or {}).get("duration") or ((leg or {}).get("GisRoute") or {}).get("durS")
                duration_minutes = parse_iso_duration_minutes(dur_iso)

                leg_dict = {
                    "origin_name": origin.get("name", ""),
                    "origin_time": f"{origin.get('date', '')} {origin.get('time', '')}".strip(),
                    "dest_name": dest.get("name", ""),
                    "dest_time": f"{dest.get('date', '')} {dest.get('time', '')}".strip(),
                    "type": leg.get("type", ""),
                    "product": product_obj.get("name", ""),
                    "direction": leg.get("direction", ""),
                    "distance": leg.get("dist"),
                    "line_number": leg.get("number") or product_obj.get("num") or product_obj.get("displayNumber"),
                    "duration": duration_minutes,
                    "category": category_full,
                }
                # attach parsed dt for sorting
                leg_dt = parse_dt(origin.get("date", ""), origin.get("time", ""))
                leg_dict["_dt"] = leg_dt
                leg_dict["_idx"] = leg.get("idx", 0)
                simplified_legs.append(leg_dict)

            # Sort legs by dt then idx for stability
            simplified_legs.sort(key=lambda x: (x.get("_dt") or datetime.max, x.get("_idx", 0)))
            # Drop helper keys
            for lg in simplified_legs:
                lg.pop("_dt", None)
                lg.pop("_idx", None)

            # Trip-level key for sorting
            first_leg_dt = None
            if simplified_legs:
                # Reparse origin_time to dt for trip key
                ot = simplified_legs[0].get("origin_time", "")
                for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                    try:
                        first_leg_dt = datetime.strptime(ot, fmt)
                        break
                    except ValueError:
                        continue
            if first_leg_dt is None:
                # fallback to trip.Origin
                torg = (trip or {}).get("Origin", {}) or {}
                first_leg_dt = parse_dt(torg.get("date", ""), torg.get("time", "")) or datetime.max

            trips_out.append({
                "index": idx,
                "legs": simplified_legs,
                "_dt": first_leg_dt,
            })

        # Sort trips by first leg datetime
        trips_out.sort(key=lambda t: t.get("_dt") or datetime.max)
        for tp in trips_out:
            tp.pop("_dt", None)
        return trips_out

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
        _direction_raw = (merged_cfg.get(CONF_DIRECTION) or "")
        direction_tokens = [t.strip().lower() for t in _direction_raw.split(",") if t.strip()]
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
            if not direction_tokens:
                return True
            destination = item.get("route", {}).get("direction", "")
            dest_lower = destination.lower()
            return any(tok in dest_lower for tok in direction_tokens)

        filtered = [it for it in raw_items if match_line(it) and match_direction(it)]
        _LOGGER.debug(
            "Filtered %d -> %d items (lines=%s direction_substr='%s')",
            len(raw_items),
            len(filtered),
            line_filter or "*",
            ",".join(direction_tokens) if direction_tokens else "*",
        )
        return filtered
