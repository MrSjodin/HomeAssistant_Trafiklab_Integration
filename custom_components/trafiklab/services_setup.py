"""Services for Trafiklab integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import TrafikLabApiClient
from .const import (
    DOMAIN,
    SERVICE_STOP_LOOKUP,
    CONF_API_KEY,
    ATTR_SEARCH_QUERY,
    ATTR_STOPS_FOUND,
)

_LOGGER = logging.getLogger(__name__)

STOP_LOOKUP_SCHEMA = vol.Schema({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(ATTR_SEARCH_QUERY): cv.string,
})


def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Trafiklab."""
    _LOGGER.debug("[Trafiklab] async_setup_services invoked")
    if hass.services.has_service(DOMAIN, SERVICE_STOP_LOOKUP):
        _LOGGER.debug("[Trafiklab] Service %s.%s already registered - skipping", DOMAIN, SERVICE_STOP_LOOKUP)
        return

    async def handle_stop_lookup(call: ServiceCall) -> dict[str, Any]:
        """Handle stop lookup service call."""
        api_key = call.data[CONF_API_KEY]
        search_query = call.data[ATTR_SEARCH_QUERY]

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


def async_remove_services(hass: HomeAssistant) -> None:
    """Remove services for Trafiklab."""
    hass.services.async_remove(DOMAIN, SERVICE_STOP_LOOKUP)
