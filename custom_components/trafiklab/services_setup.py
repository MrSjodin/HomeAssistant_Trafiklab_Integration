"""Services for Trafiklab integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TrafikLabApiClient
from .const import (
    DOMAIN,
    SERVICE_STOP_LOOKUP,
    SERVICE_UPDATE_NOW,
    SERVICE_TRAVEL_SEARCH,
    CONF_API_KEY,
    CONF_ORIGIN,
    CONF_ORIGIN_TYPE,
    CONF_DESTINATION,
    CONF_DESTINATION_TYPE,
    CONF_VIA,
    CONF_MAX_WALKING_DISTANCE,
    CONF_MAX_TRIP_DURATION,
    CONF_TRANSPORT_MODES,
    ATTR_SEARCH_QUERY,
    ATTR_STOPS_FOUND,
    RESROBOT_PRODUCTS_MAP,
    CONF_SENSOR_TYPE,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_RESROBOT,
    CONF_INCLUDE_PLATFORM,
    CONF_REALTIME_API_KEY,
)
from .coordinator import enrich_platform_for_trips
from .sensor import normalize_resrobot_trips

_LOGGER = logging.getLogger(__name__)

STOP_LOOKUP_SCHEMA = vol.Schema({
    vol.Optional(CONF_API_KEY): cv.string,
    vol.Optional("config_entry_id"): cv.string,
    vol.Required(ATTR_SEARCH_QUERY): cv.string,
})

UPDATE_NOW_SCHEMA = vol.Schema({
    vol.Optional("config_entry_id"): cv.string,
})

TRAVEL_SEARCH_SCHEMA = vol.Schema({
    vol.Optional(CONF_API_KEY): cv.string,
    vol.Optional(CONF_REALTIME_API_KEY): cv.string,
    vol.Optional("config_entry_id"): cv.string,
    vol.Required(CONF_ORIGIN): cv.string,
    vol.Required(CONF_DESTINATION): cv.string,
    vol.Optional(CONF_ORIGIN_TYPE, default="stop_id"): vol.In(["stop_id", "coordinates", "name", "zone", "person"]),
    vol.Optional(CONF_DESTINATION_TYPE, default="stop_id"): vol.In(["stop_id", "coordinates", "name", "zone", "person"]),
    vol.Optional(CONF_VIA, default=""): cv.string,
    vol.Optional(CONF_MAX_WALKING_DISTANCE, default=1000): vol.All(vol.Coerce(int), vol.Range(min=0)),
    vol.Optional(CONF_TRANSPORT_MODES, default=list): vol.All(
        cv.ensure_list,
        [vol.In(list(RESROBOT_PRODUCTS_MAP.keys()))],
    ),
    vol.Optional(CONF_MAX_TRIP_DURATION, default=None): vol.Any(
        None, vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))
    ),
    vol.Optional(CONF_INCLUDE_PLATFORM, default=False): bool,
})


def _resolve_realtime_api_key(hass: HomeAssistant, call_data: dict) -> str | None:
    """Resolve a Realtime API key for the stop-lookup / departure / arrival APIs.

    Resolution order:
      1. Explicit ``api_key`` in call_data
      2. Key from the entry identified by ``config_entry_id`` in call_data
      3. Key from the first departure or arrival config entry in hass.data
    """
    if key := call_data.get(CONF_API_KEY):
        return key
    domain_data: dict = hass.data.get(DOMAIN, {})
    entry_id: str | None = call_data.get("config_entry_id")
    if entry_id:
        coordinator = domain_data.get(entry_id)
        if coordinator is None:
            raise ServiceValidationError(
                f"Config entry '{entry_id}' was not found for {DOMAIN}."
            )
        if coordinator.entry.data.get(CONF_SENSOR_TYPE) not in (SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL):
            raise ServiceValidationError(
                f"Config entry '{entry_id}' is not a departure or arrival entry — "
                "only departure/arrival entries carry a Realtime API key."
            )
        return coordinator.entry.data.get(CONF_API_KEY)
    for coordinator in domain_data.values():
        if coordinator.entry.data.get(CONF_SENSOR_TYPE) in (SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL):
            return coordinator.entry.data.get(CONF_API_KEY)
    return None


def _resolve_resrobot_api_key(hass: HomeAssistant, call_data: dict) -> str | None:
    """Resolve a Resrobot API key for the travel-search API.

    Resolution order:
      1. Explicit ``api_key`` in call_data
      2. Key from the entry identified by ``config_entry_id`` in call_data
      3. Key from the first Resrobot travel_search config entry in hass.data
    """
    if key := call_data.get(CONF_API_KEY):
        return key
    domain_data: dict = hass.data.get(DOMAIN, {})
    entry_id: str | None = call_data.get("config_entry_id")
    if entry_id:
        coordinator = domain_data.get(entry_id)
        if coordinator is None:
            raise ServiceValidationError(
                f"Config entry '{entry_id}' was not found for {DOMAIN}."
            )
        if coordinator.entry.data.get(CONF_SENSOR_TYPE) != SENSOR_TYPE_RESROBOT:
            raise ServiceValidationError(
                f"Config entry '{entry_id}' is not a Resrobot travel-search entry."
            )
        return coordinator.entry.data.get(CONF_API_KEY)
    for coordinator in domain_data.values():
        if coordinator.entry.data.get(CONF_SENSOR_TYPE) == SENSOR_TYPE_RESROBOT:
            return coordinator.entry.data.get(CONF_API_KEY)
    return None


def _find_realtime_key_from_entries(hass: HomeAssistant) -> str | None:
    """Return the Realtime API key from the first departure or arrival config entry.

    "First" here means the first entry encountered during iteration over the
    DOMAIN data dict (arbitrary / insertion order). Any departure or arrival
    entry will work because they all carry the same type of Realtime API key.

    Used by ``travel_search`` platform enrichment so the Resrobot ``api_key``
    field is never mistaken for a Realtime/Timetable key.
    """
    domain_data: dict = hass.data.get(DOMAIN, {})
    for coordinator in domain_data.values():
        if (
            hasattr(coordinator, "entry")
            and coordinator.entry.data.get(CONF_SENSOR_TYPE)
            in (SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL)
        ):
            return coordinator.entry.data.get(CONF_API_KEY)
    return None


def _validate_coordinates(value: str) -> bool:
    """Return True when *value* is a valid ``'lat,lon'`` string."""
    try:
        lat, lon = value.split(",")
        _lat = float(lat)
        _lon = float(lon)
        return True
    except (ValueError, AttributeError):
        return False


def _resolve_zone_coordinates(hass: HomeAssistant, value: str) -> str | None:
    """Resolve a zone name or entity_id to a 'lat,lon' string.

    Resolution order:
    1. Direct lowercase match: ``"home"`` → ``zone.home``, ``"zone.home"`` → ``zone.home``.
    2. Slugified match: ``"My Home"`` → ``zone.my_home`` (spaces/special chars → underscores).
    3. Friendly-name scan: case-insensitive match on the zone's ``friendly_name`` attribute.

    Returns ``None`` if the zone entity does not exist or has no location attributes.
    """
    stripped = value.strip()

    # 1. Direct lowercase match (handles "home", "Home", "zone.home")
    normalized = stripped.lower()
    if not normalized.startswith("zone."):
        normalized = f"zone.{normalized}"
    state = hass.states.get(normalized)

    # 2. Slugified match (handles multi-word names like "My Home" → zone.my_home)
    if state is None:
        slug = re.sub(r"[^a-z0-9]+", "_", stripped.lower()).strip("_")
        slugged = slug if slug.startswith("zone.") else f"zone.{slug}"
        if slugged != normalized:
            state = hass.states.get(slugged)

    # 3. Friendly-name scan (handles names with accents or that differ from the entity slug)
    if state is None:
        lower = stripped.lower()
        for zone_state in hass.states.async_all("zone"):
            friendly = (zone_state.attributes.get("friendly_name") or "").lower()
            if friendly == lower:
                state = zone_state
                break

    if state is None:
        return None
    lat = state.attributes.get("latitude")
    lon = state.attributes.get("longitude")
    if lat is None or lon is None:
        return None
    return f"{lat},{lon}"


def _resolve_person_coordinates(hass: HomeAssistant, entity_id: str) -> str | None:
    """Resolve a person or device_tracker entity to a 'lat,lon' string.

    Tries direct GPS attributes first (set when the device reports location).
    Falls back to the zone that the entity's state names (e.g. state = 'home').
    Returns ``None`` if neither source is available.
    """
    state = hass.states.get(entity_id)
    if state is None:
        return None
    lat = state.attributes.get("latitude")
    lon = state.attributes.get("longitude")
    if lat is not None and lon is not None:
        return f"{lat},{lon}"
    # Fallback: entity is in a known zone (state == zone name)
    return _resolve_zone_coordinates(hass, state.state)


def _extract_resrobot_stops(stop_result: dict) -> list[dict]:
    """Extract a normalised stop list from a Resrobot /location.name response.

    Handles two known response shapes:
      - ``{"StopLocation": [...]}``  (classic Hafas)
      - ``{"stopLocationOrCoordLocation": [...]}``  (newer Hafas)
    Also handles the case where the API returns a single dict instead of a list.

    Only actual stop objects are returned. In particular,
    ``stopLocationOrCoordLocation`` may contain wrappers like
    ``{"CoordLocation": {...}}`` which must not be treated as stops.
    """
    result = stop_result or {}
    stops: list[dict] = []

    raw_stops = result.get("StopLocation") or []
    if isinstance(raw_stops, dict):
        raw_stops = [raw_stops]
    for item in raw_stops:
        if isinstance(item, dict):
            stops.append(item)

    raw_mixed_locations = result.get("stopLocationOrCoordLocation") or []
    if isinstance(raw_mixed_locations, dict):
        raw_mixed_locations = [raw_mixed_locations]
    for item in raw_mixed_locations:
        if not isinstance(item, dict):
            continue
        stop_location = item.get("StopLocation")
        if isinstance(stop_location, dict):
            stops.append(stop_location)

    return stops


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Trafiklab."""
    _LOGGER.debug("[Trafiklab] async_setup_services invoked")

    async def handle_stop_lookup(call: ServiceCall) -> dict[str, Any]:
        """Handle stop lookup service call."""
        search_query = call.data[ATTR_SEARCH_QUERY]
        api_key = _resolve_realtime_api_key(hass, call.data)
        if not api_key:
            return {
                "search_query": search_query,
                "stops_found": [],
                "total_stops": 0,
                "error": (
                    "No Realtime API key available — add a departure or arrival sensor "
                    "or pass api_key explicitly"
                ),
            }

        session = async_get_clientsession(hass)
        async with TrafikLabApiClient(api_key, session=session) as client:
            try:
                result = await client.search_stops(search_query)

                if not result or "stop_groups" not in result:
                    return {
                        "search_query": search_query,
                        "stops_found": [],
                        "total_stops": 0,
                        "error": "No stops found",
                    }

                stops_found: list[dict[str, Any]] = []
                for stop_group in result["stop_groups"]:
                    stops_found.append(
                        {
                            "id": stop_group.get("id", ""),
                            "name": stop_group.get("name", ""),
                            "area_type": stop_group.get("area_type", ""),
                            "transport_modes": stop_group.get("transport_modes", []),
                            "average_daily_departures": stop_group.get(
                                "average_daily_stop_times", 0
                            ),
                            "child_stops": [
                                {
                                    "id": stop.get("id", ""),
                                    "name": stop.get("name", ""),
                                    "lat": stop.get("lat", 0),
                                    "lon": stop.get("lon", 0),
                                }
                                for stop in stop_group.get("stops", [])
                            ],
                        }
                    )

                return {
                    "search_query": search_query,
                    "stops_found": stops_found,
                    "total_stops": len(stops_found),
                }

            except Exception as err:  # pragma: no cover - runtime safety
                _LOGGER.error("Error during stop lookup: %s", err)
                return {
                    "search_query": search_query,
                    "stops_found": [],
                    "total_stops": 0,
                    "error": str(err),
                }

    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_LOOKUP,
        handle_stop_lookup,
        schema=STOP_LOOKUP_SCHEMA,
        supports_response=True,
    )
    _LOGGER.info("[Trafiklab] Registered service %s.%s (simple mode)", DOMAIN, SERVICE_STOP_LOOKUP)

    async def handle_update_now(call: ServiceCall) -> None:
        """Handle update_now service call."""
        entry_id: str | None = call.data.get("config_entry_id")
        domain_data: dict = hass.data.get(DOMAIN, {})

        if entry_id is not None:
            coordinator = domain_data.get(entry_id)
            if coordinator is None:
                raise ServiceValidationError(
                    f"No active Trafiklab config entry with id '{entry_id}'"
                )
            await coordinator.async_request_refresh()
        else:
            for coordinator in domain_data.values():
                await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_UPDATE_NOW,
        handle_update_now,
        schema=UPDATE_NOW_SCHEMA,
    )
    _LOGGER.info("[Trafiklab] Registered service %s.%s", DOMAIN, SERVICE_UPDATE_NOW)

    if not hass.services.has_service(DOMAIN, SERVICE_TRAVEL_SEARCH):

        async def handle_travel_search(call: ServiceCall) -> dict[str, Any]:
            """Handle travel search service call."""
            api_key = _resolve_resrobot_api_key(hass, call.data)
            if not api_key:
                return {
                    "trips": [],
                    "total_trips": 0,
                    "error": (
                        "No Resrobot API key available — add a Resrobot travel search sensor "
                        "or pass api_key explicitly"
                    ),
                }
            origin: str = call.data[CONF_ORIGIN]
            destination: str = call.data[CONF_DESTINATION]
            origin_type: str = call.data.get(CONF_ORIGIN_TYPE, "stop_id")
            destination_type: str = call.data.get(CONF_DESTINATION_TYPE, "stop_id")
            via: str = call.data.get(CONF_VIA, "") or ""
            max_walking_distance: int = call.data.get(CONF_MAX_WALKING_DISTANCE, 1000)
            transport_modes: list[str] = call.data.get(CONF_TRANSPORT_MODES) or []
            max_trip_duration: int | None = call.data.get(CONF_MAX_TRIP_DURATION)
            include_platform: bool = bool(call.data.get(CONF_INCLUDE_PLATFORM, False))

            response: dict[str, Any] = {}
            session = async_get_clientsession(hass)
            # Name resolution uses the Resrobot /location.name endpoint (same key,
            # same client) so the returned extId is already a national stop ID.
            async with TrafikLabApiClient(api_key, session=session) as client:
                try:
                    if origin_type == "zone":
                        coords = _resolve_zone_coordinates(hass, origin)
                        if coords is None:
                            return {
                                "trips": [],
                                "total_trips": 0,
                                "error": f"Could not resolve zone '{origin}' — zone entity not found or has no location",
                            }
                        response["resolved_origin_coords"] = coords
                        origin = coords
                        origin_type = "coordinates"

                    if origin_type == "person":
                        coords = _resolve_person_coordinates(hass, origin)
                        if coords is None:
                            return {
                                "trips": [],
                                "total_trips": 0,
                                "error": f"Could not resolve person/device_tracker location for '{origin}'",
                            }
                        response["resolved_origin_coords"] = coords
                        origin = coords
                        origin_type = "coordinates"

                    if destination_type == "zone":
                        coords = _resolve_zone_coordinates(hass, destination)
                        if coords is None:
                            return {
                                "trips": [],
                                "total_trips": 0,
                                "error": f"Could not resolve zone '{destination}' — zone entity not found or has no location",
                            }
                        response["resolved_destination_coords"] = coords
                        destination = coords
                        destination_type = "coordinates"

                    if destination_type == "person":
                        coords = _resolve_person_coordinates(hass, destination)
                        if coords is None:
                            return {
                                "trips": [],
                                "total_trips": 0,
                                "error": f"Could not resolve person/device_tracker location for '{destination}'",
                            }
                        response["resolved_destination_coords"] = coords
                        destination = coords
                        destination_type = "coordinates"

                    if origin_type == "name":
                        stop_result = await client.search_resrobot_stops(origin, api_key)
                        stops = _extract_resrobot_stops(stop_result)
                        if not stops:
                            return {
                                "trips": [],
                                "total_trips": 0,
                                "error": f"Could not resolve origin stop name: {origin}",
                            }
                        resolved_origin = stops[0].get("extId") or stops[0].get("id", "")
                        response["resolved_origin_id"] = resolved_origin
                        origin_type = "stop_id"
                        origin = resolved_origin

                    if destination_type == "name":
                        stop_result = await client.search_resrobot_stops(destination, api_key)
                        stops = _extract_resrobot_stops(stop_result)
                        if not stops:
                            return {
                                "trips": [],
                                "total_trips": 0,
                                "error": f"Could not resolve destination stop name: {destination}",
                            }
                        resolved_destination = stops[0].get("extId") or stops[0].get("id", "")
                        response["resolved_destination_id"] = resolved_destination
                        destination_type = "stop_id"
                        destination = resolved_destination

                    known_transport_modes = []
                    if transport_modes:
                        known_transport_modes = [
                            mode for mode in transport_modes if mode in RESROBOT_PRODUCTS_MAP
                        ]

                    # Validate coordinates now that all resolution is done.
                    # Zone/person resolution already produces valid 'lat,lon' strings,
                    # but user-supplied coordinates must be checked explicitly.
                    if origin_type == "coordinates" and not _validate_coordinates(origin):
                        return {
                            "trips": [],
                            "total_trips": 0,
                            "error": (
                                f"Invalid coordinates for origin: '{origin}' "
                                "— expected 'lat,lon' (e.g. '59.33,18.07')"
                            ),
                        }
                    if destination_type == "coordinates" and not _validate_coordinates(destination):
                        return {
                            "trips": [],
                            "total_trips": 0,
                            "error": (
                                f"Invalid coordinates for destination: '{destination}' "
                                "— expected 'lat,lon' (e.g. '59.33,18.07')"
                            ),
                        }

                    product_requests: list[int | None]
                    if known_transport_modes:
                        product_requests = [
                            RESROBOT_PRODUCTS_MAP[mode] for mode in known_transport_modes
                        ]
                    else:
                        product_requests = [None]

                    trips_raw: list[dict[str, Any]] = []
                    for products in product_requests:
                        result = await client.get_resrobot_travel_search(
                            api_key,
                            origin_type,
                            origin,
                            destination_type,
                            destination,
                            via,
                            "",
                            max_walking_distance,
                            products,
                        )
                        trips_raw.extend((result or {}).get("Trip") or [])

                    if include_platform:
                        realtime_key = (
                            call.data.get(CONF_REALTIME_API_KEY)
                            or _find_realtime_key_from_entries(hass)
                        )
                        if realtime_key:
                            try:
                                await enrich_platform_for_trips(
                                    trips_raw, realtime_key, session
                                )
                            except Exception as perr:
                                _LOGGER.warning("Platform enrichment failed in travel_search: %s", perr)
                        else:
                            _LOGGER.warning(
                                "include_platform requested but no Realtime API key available "
                                "(add a departure/arrival sensor or pass realtime_api_key explicitly)"
                            )

                    trips = normalize_resrobot_trips(trips_raw, max_trip_duration)
                    response.update({"trips": trips, "total_trips": len(trips)})
                    return response

                except Exception as err:
                    _LOGGER.error("Error during travel search: %s", err)
                    response.update({"trips": [], "total_trips": 0, "error": str(err)})
                    return response

        hass.services.async_register(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            handle_travel_search,
            schema=TRAVEL_SEARCH_SCHEMA,
            supports_response=True,
        )
        _LOGGER.info("[Trafiklab] Registered service %s.%s", DOMAIN, SERVICE_TRAVEL_SEARCH)


def async_remove_services(hass: HomeAssistant) -> None:
    """Remove services for Trafiklab.

    ``travel_search`` is intentionally left registered because it can operate
    without any loaded config entry when the caller supplies an explicit API
    key (and it is also available from the YAML stub setup path). Removing it
    when the last entry is unloaded makes the ad-hoc service disappear until
    Home Assistant restarts.
    """
    hass.services.async_remove(DOMAIN, SERVICE_STOP_LOOKUP)
    hass.services.async_remove(DOMAIN, SERVICE_UPDATE_NOW)
