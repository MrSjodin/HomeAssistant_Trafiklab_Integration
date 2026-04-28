"""Data update coordinator for Trafiklab."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.template import Template
from homeassistant.exceptions import TemplateError

from .const import (
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_SENSOR_TYPE,
    CONF_REFRESH_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_RESROBOT,
    CONF_UPDATE_CONDITION,
    CONF_TRANSPORT_MODES,
    RESROBOT_PRODUCTS_MAP,
)
from .api import TrafikLabApiClient
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)


class TrafikLabCoordinator(DataUpdateCoordinator):
    """Data update coordinator for Trafiklab."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        # Use HA shared aiohttp session
        session = async_get_clientsession(hass)
        self.api_client = TrafikLabApiClient(entry.data[CONF_API_KEY], session=session)
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
            # Optional: evaluate update condition template from options
            update_condition_tmpl = (self.entry.options.get(CONF_UPDATE_CONDITION) or "").strip()
            if update_condition_tmpl:
                try:
                    rendered = Template(update_condition_tmpl, self.hass).async_render(None)
                    if isinstance(rendered, str):
                        cond = rendered.strip().lower() == "true"
                    else:
                        cond = bool(rendered)
                    if not cond:
                        _LOGGER.debug("Update condition evaluated to false; skipping API call")
                        # Return the last known data (do not mark update as failed)
                        return self.data or {}
                except TemplateError as terr:
                    _LOGGER.warning("Update condition template error: %s", terr)
                    # Proceed with update to avoid stalling sensor
            # Merge data + options (options override)
            # Base immutable data lives in entry.data (api key, stop id, sensor_type, name)
            # Mutable settings now live in options (migration safe fallback to data)
            sensor_type = self.entry.data.get(CONF_SENSOR_TYPE, SENSOR_TYPE_DEPARTURE)
            if sensor_type == SENSOR_TYPE_RESROBOT:
                # Gather Resrobot parameters
                base = self.entry.data
                opts = self.entry.options
                api_key = base[CONF_API_KEY]
                origin_type = base.get("origin_type", "stop_id")
                origin = base.get("origin", "")
                destination_type = base.get("destination_type", "stop_id")
                destination = base.get("destination", "")
                via = opts.get("via", "")
                avoid = opts.get("avoid", "")
                max_walking_distance = opts.get("max_walking_distance", 1000)
                # Build per-mode products bitmasks so each mode gets a fair set of
                # results.  When only a single mode (or no filter) is selected we
                # keep the existing single-call behaviour.  When multiple modes are
                # selected we issue one parallel request per mode and merge the
                # trips afterwards – this prevents the route planner from filling
                # all result slots with the fastest mode only.
                transport_modes = opts.get(CONF_TRANSPORT_MODES) or []
                known_modes = [m for m in transport_modes if m in RESROBOT_PRODUCTS_MAP]

                async def _fetch_for_products(products_bitmask: int | None) -> dict:
                    return await self.api_client.get_resrobot_travel_search(
                        api_key,
                        origin_type,
                        origin,
                        destination_type,
                        destination,
                        via,
                        avoid,
                        max_walking_distance,
                        products_bitmask,
                    )

                if len(known_modes) > 1:
                    # One request per mode – run concurrently
                    _LOGGER.debug(
                        "Fetching Resrobot travel search with %d separate mode calls: %s → %s",
                        len(known_modes), origin, destination,
                    )
                    per_mode_results = await asyncio.gather(
                        *[_fetch_for_products(RESROBOT_PRODUCTS_MAP[m]) for m in known_modes]
                    )
                    # Merge Trip lists from all responses; keep the first response's
                    # metadata envelope (Trip is the only field we care about).
                    merged_trips: list = []
                    seen_trip_keys: set = set()
                    for result in per_mode_results:
                        for trip in (result or {}).get("Trip") or []:
                            # Deduplicate by (first-leg origin/dest names + departure time)
                            legs = (((trip or {}).get("LegList") or {}).get("Leg")) or []
                            if isinstance(legs, dict):
                                legs = [legs]
                            first_leg = legs[0] if legs else {}
                            last_leg = legs[-1] if legs else {}
                            trip_key = (
                                (first_leg.get("Origin") or {}).get("name", ""),
                                (first_leg.get("Origin") or {}).get("date", ""),
                                (first_leg.get("Origin") or {}).get("time", ""),
                                (last_leg.get("Destination") or {}).get("name", ""),
                                (last_leg.get("Destination") or {}).get("time", ""),
                            )
                            if trip_key not in seen_trip_keys:
                                seen_trip_keys.add(trip_key)
                                merged_trips.append(trip)
                    data = dict(per_mode_results[0]) if per_mode_results else {}
                    data["Trip"] = merged_trips
                else:
                    # Single mode or no filter – original single-call path
                    products: int | None = RESROBOT_PRODUCTS_MAP.get(known_modes[0]) if known_modes else None
                    _LOGGER.debug(
                        "Fetching Resrobot travel search: origin=%s, destination=%s", origin, destination,
                    )
                    data = await _fetch_for_products(products)

                # Normalize and sort trips/legs for consistent downstream usage
                try:
                    data = self._normalize_resrobot_response(data)
                except Exception as nerr:  # pragma: no cover - defensive
                    _LOGGER.debug("Resrobot normalize failed: %s", nerr)
                # Mark successful update time
                from datetime import datetime, timezone
                self.last_successful_update = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
                return data
            else:
                stop_id = self.entry.data[CONF_STOP_ID]
                _LOGGER.debug("Fetching %s for stop %s", sensor_type, stop_id)
                if sensor_type == SENSOR_TYPE_ARRIVAL:
                    data = await self.api_client.get_arrivals(stop_id)
                else:
                    data = await self.api_client.get_departures(stop_id)
                if not data:
                    _LOGGER.warning("No data received from API")
                    raise UpdateFailed("No data received from API")
                if not isinstance(data, dict):
                    _LOGGER.error("Invalid API response format: expected dict, got %s", type(data))
                    raise UpdateFailed("Invalid API response format")
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

    def _normalize_resrobot_response(self, data: dict) -> dict:
        """Ensure ResRobot response has sorted trips and legs.

        - Guarantees data["Trip"] is a list.
        - Ensures each trip's LegList.Leg is a list.
        - Sorts trips by first leg origin datetime (ascending).
        - Sorts legs within each trip by origin datetime (ascending).
        """
        from datetime import datetime

        if not isinstance(data, dict):
            return data

        trips = data.get("Trip")
        if trips is None:
            data["Trip"] = []
            return data
        if isinstance(trips, dict):
            trips = [trips]

        def parse_dt(leg: dict) -> tuple:
            org = leg.get("Origin", {}) or {}
            d = org.get("date") or org.get("rtDate") or "9999-12-31"
            t = org.get("time") or org.get("rtTime") or "23:59:59"
            # Try with seconds, fallback without
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return (datetime.strptime(f"{d} {t}", fmt),)
                except Exception:
                    continue
            # Unparsable -> push to end, include secondary sort key to keep stability
            return (datetime.max,)

        normalized_trips: list[dict] = []
        for trip in trips:
            legs = (((trip or {}).get("LegList") or {}).get("Leg"))
            if legs is None:
                legs_list: list[dict] = []
            elif isinstance(legs, dict):
                legs_list = [legs]
            else:
                legs_list = list(legs)
            # Sort legs by origin datetime
            legs_list.sort(key=lambda lg: (parse_dt(lg)[0], lg.get("idx", 0)))
            # Write back sorted list
            trip = dict(trip or {})
            leglist = dict((trip.get("LegList") or {}))
            leglist["Leg"] = legs_list
            trip["LegList"] = leglist
            normalized_trips.append(trip)

        # Sort trips by their first leg datetime or trip-level Origin
        def trip_key(tp: dict):
            legs_list = (((tp or {}).get("LegList") or {}).get("Leg")) or []
            if legs_list:
                return parse_dt(legs_list[0])[0]
            # fallback to trip-level Origin
            org = (tp or {}).get("Origin", {}) or {}
            d = org.get("date") or "9999-12-31"
            t = org.get("time") or "23:59:59"
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(f"{d} {t}", fmt)
                except Exception:
                    continue
            return datetime.max

        normalized_trips.sort(key=trip_key)
        data["Trip"] = normalized_trips
        return data
