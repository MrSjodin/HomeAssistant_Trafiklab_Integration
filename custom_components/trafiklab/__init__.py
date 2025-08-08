"""The Trafiklab integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DOMAIN, 
    SERVICE_STOP_LOOKUP,
    CONF_API_KEY,
    ATTR_SEARCH_QUERY,
    ATTR_STOPS_FOUND,
)
from .coordinator import TrafikLabCoordinator
from .api import TrafikLabApiClient
from .translation_helper import TranslationHelper, set_translation_helper

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

# Service schemas
STOP_LOOKUP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(ATTR_SEARCH_QUERY): cv.string,
    }
)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafiklab from a config entry."""
    _LOGGER.debug("Setting up Trafiklab integration")
    
    # Initialize translation helper with Home Assistant's language preference
    language = hass.config.language or "en"
    translation_helper = TranslationHelper(hass, language)
    set_translation_helper(translation_helper)
    
    coordinator = TrafikLabCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Add listener for config entry updates
    entry.async_on_unload(
        entry.add_update_listener(update_listener)
    )
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    async def handle_stop_lookup(call: ServiceCall) -> dict[str, any]:
        """Handle stop lookup service call."""
        api_key = call.data[CONF_API_KEY]
        search_query = call.data[ATTR_SEARCH_QUERY]
        
        async with TrafikLabApiClient(api_key) as client:
            try:
                result = await client.search_stops(search_query)
                
                if not result or "stop_groups" not in result:
                    error_msg = "No stops found"
                    hass.bus.async_fire(
                        f"{DOMAIN}_stop_lookup_error",
                        {
                            ATTR_SEARCH_QUERY: search_query,
                            "error": error_msg,
                        }
                    )
                    return {
                        "search_query": search_query,
                        "stops_found": [],
                        "total_stops": 0,
                        "error": error_msg,
                    }
                
                # Process the results
                stops_found = []
                for stop_group in result["stop_groups"]:
                    stops_found.append({
                        "id": stop_group.get("id", ""),
                        "name": stop_group.get("name", ""),
                        "area_type": stop_group.get("area_type", ""),
                        "transport_modes": stop_group.get("transport_modes", []),
                        "average_daily_departures": stop_group.get("average_daily_stop_times", 0),
                        "child_stops": [
                            {
                                "id": stop.get("id", ""),
                                "name": stop.get("name", ""),
                                "lat": stop.get("lat", 0),
                                "lon": stop.get("lon", 0),
                            }
                            for stop in stop_group.get("stops", [])
                        ]
                    })
                
                # Fire event with results (for backward compatibility)
                hass.bus.async_fire(
                    f"{DOMAIN}_stop_lookup_result",
                    {
                        ATTR_SEARCH_QUERY: search_query,
                        ATTR_STOPS_FOUND: stops_found,
                    }
                )
                
                # Return data for service response (visible on Services page)
                return {
                    "search_query": search_query,
                    "stops_found": stops_found,
                    "total_stops": len(stops_found),
                }
                
            except Exception as err:
                error_msg = str(err)
                _LOGGER.error("Error during stop lookup: %s", error_msg)
                hass.bus.async_fire(
                    f"{DOMAIN}_stop_lookup_error",
                    {
                        ATTR_SEARCH_QUERY: search_query,
                        "error": error_msg,
                    }
                )
                return {
                    "search_query": search_query,
                    "stops_found": [],
                    "total_stops": 0,
                    "error": error_msg,
                }
    
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_LOOKUP,
        handle_stop_lookup,
        schema=STOP_LOOKUP_SCHEMA,
        supports_response=True,
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Trafiklab integration")
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove service if this is the last entry
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_STOP_LOOKUP)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
