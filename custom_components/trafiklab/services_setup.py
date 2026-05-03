"""Services for Trafiklab integration."""
from __future__ import annotations

import logging
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
)
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
        return coordinator.entry.data.get(CONF_API_KEY) if coordinator else None
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
        return coordinator.entry.data.get(CONF_API_KEY) if coordinator else None
    for coordinator in domain_data.values():
        if coordinator.entry.data.get(CONF_SENSOR_TYPE) == SENSOR_TYPE_RESROBOT:
            return coordinator.entry.data.get(CONF_API_KEY)
    return None


def _resolve_zone_coordinates(hass: HomeAssistant, value: str) -> str | None:
    """Resolve a zone name or entity_id to a 'lat,lon' string.

    Accepts ``"home"``, ``"Home"``, or ``"zone.home"`` — all normalised the same way.
    Returns ``None`` if the zone entity does not exist or has no location attributes.
    """
    normalized = value.strip().lower()
    if not normalized.startswith("zone."):
        normalized = f"zone.{normalized}"
    state = hass.states.get(normalized)
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
    """
    raw = (
        (stop_result or {}).get("StopLocation")
        or (stop_result or {}).get("stopLocationOrCoordLocation")
        or []
    )
    if isinstance(raw, dict):
        raw = [raw]
    # stopLocationOrCoordLocation entries are wrapped: {"StopLocation": {...}}
    stops: list[dict] = []
    for item in raw:
        if isinstance(item, dict) and "StopLocation" in item:
            stops.append(item["StopLocation"])
        elif isinstance(item, dict):
            stops.append(item)
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

                    products: int | None = None
                    if transport_modes:
                        known = [m for m in transport_modes if m in RESROBOT_PRODUCTS_MAP]
                        if known:
                            products = sum(RESROBOT_PRODUCTS_MAP[m] for m in known)

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

                    trips_raw = (result or {}).get("Trip") or []
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
    """Remove services for Trafiklab."""
    hass.services.async_remove(DOMAIN, SERVICE_STOP_LOOKUP)
    hass.services.async_remove(DOMAIN, SERVICE_UPDATE_NOW)
    hass.services.async_remove(DOMAIN, SERVICE_TRAVEL_SEARCH)
