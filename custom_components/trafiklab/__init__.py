"""The Trafiklab integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TrafikLabCoordinator
from .services_setup import async_setup_services, async_remove_services

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

# Allow an (optional) empty YAML stub `trafiklab:` so the integration loads at
# startup and registers its services even before any config entry is created.
# Users who only want to use the stop_lookup service can add this stub.
CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({}, extra=vol.PREVENT_EXTRA)}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Trafiklab at Home Assistant start (register services)."""
    # Ensure services are available even before any config entry is created.
    _LOGGER.info("[Trafiklab] async_setup called - registering services early")
    async_setup_services(hass)
    
    # Fallback: ensure services registered once HA fully started
    async def _register_late(_: object) -> None:
        _LOGGER.debug("[Trafiklab] Late startup service registration check")
        async_setup_services(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _register_late)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Trafiklab from a config entry."""
    _LOGGER.info("[Trafiklab] Setting up config entry %s", entry.entry_id)
    coordinator = TrafikLabCoordinator(hass, entry)
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Set up services (only once)
    _LOGGER.debug("[Trafiklab] Ensuring services registered during entry setup")
    async_setup_services(hass)
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Schedule initial data fetch without blocking setup
    hass.async_create_task(
        coordinator.async_config_entry_first_refresh()
    )

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the entry."""
    _LOGGER.debug("Options updated for entry %s, reloading", entry.entry_id)
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: D401
    """Migrate config entry to latest version structure.

    Version 1 -> 2: Move mutable settings (line_filter, direction, time_window, refresh_interval)
    from data to options to avoid redundancy and allow UI edits without changing core data.
    """
    if entry.version == 1:
        data = dict(entry.data)
        options = dict(entry.options)
        moved_keys = [
            "line_filter",
            "direction",
            "time_window",
            "refresh_interval",
        ]
        changed = False
        for key in moved_keys:
            if key in data and key not in options:
                options[key] = data.pop(key)
                changed = True
        if changed:
            hass.config_entries.async_update_entry(entry, data=data, options=options, version=2)
            _LOGGER.debug("Migrated Trafiklab entry %s to version 2 (moved mutable keys to options)", entry.entry_id)
        else:
            hass.config_entries.async_update_entry(entry, version=2)
        return True
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
