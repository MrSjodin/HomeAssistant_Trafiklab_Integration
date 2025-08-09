"""The Trafiklab integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TrafikLabCoordinator
from .services_setup import async_setup_services, async_remove_services

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafiklab from a config entry."""
    coordinator = TrafikLabCoordinator(hass, entry)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up services (only once)
    async_setup_services(hass)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Schedule initial data fetch without blocking setup
    hass.async_create_task(
        coordinator.async_config_entry_first_refresh()
    )
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Remove services if no more entries
        if not hass.data[DOMAIN]:
            async_remove_services(hass)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
