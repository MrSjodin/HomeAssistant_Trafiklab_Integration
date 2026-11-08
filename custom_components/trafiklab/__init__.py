"""The Trafiklab integration."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir

from .const import (
    DOMAIN,
    CONF_SENSOR_TYPE,
    CONF_TIME_WINDOW,
    REALTIME_WINDOW_MINUTES,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_DEPARTURE,
)
from .coordinator import TrafikLabCoordinator
from .services_setup import async_setup_services, async_remove_services

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.CALENDAR]

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


_VALID_TRANSPORT_MODES: frozenset[str] = frozenset({"bus", "metro", "train", "tram", "boat"})


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:  # noqa: D401
    """Migrate config entry to latest version structure.

    Version 1 -> 2: Move mutable settings (line_filter, direction, time_window, refresh_interval)
    from data to options to avoid redundancy and allow UI edits without changing core data.
    Also normalises transport_modes: moves it from data to options if present, removes any
    values no longer in the valid set (e.g. the old "ship" key), and ensures the value is a list.

    Version 2 -> 3: Cap any configured time_window greater than the Trafiklab Timetable
    (Realtime) API's fixed 60-minute window down to 60 minutes, for Departure/Arrival
    sensors only. Multi-request support for windows beyond 60 minutes now exists (see
    coordinator.TrafikLabCoordinator._fetch_realtime_window), but it increases the
    number of API calls made on every refresh, so it must be explicitly re-enabled by
    the user rather than silently taking effect for existing entries. A repair issue
    is raised for each affected entry so the change is visible.
    """
    original_version = entry.version
    data = dict(entry.data)
    options = dict(entry.options)
    changed = False

    if original_version == 1:
        moved_keys = [
            "line_filter",
            "direction",
            "time_window",
            "refresh_interval",
        ]
        for key in moved_keys:
            if key in data and key not in options:
                options[key] = data.pop(key)
                changed = True

        # Move transport_modes from data → options if it ended up there.
        if "transport_modes" in data and "transport_modes" not in options:
            options["transport_modes"] = data.pop("transport_modes")
            changed = True

        # Normalise transport_modes in options: must be a list of valid strings.
        raw_modes = options.get("transport_modes")
        if not isinstance(raw_modes, list):
            options["transport_modes"] = []
            changed = True
        else:
            cleaned = [m for m in raw_modes if m in _VALID_TRANSPORT_MODES]
            if cleaned != raw_modes:
                options["transport_modes"] = cleaned
                changed = True

    if original_version <= 2:
        if data.get(CONF_SENSOR_TYPE) in (SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL):
            current_window = options.get(CONF_TIME_WINDOW)
            if isinstance(current_window, (int, float)) and current_window > REALTIME_WINDOW_MINUTES:
                options[CONF_TIME_WINDOW] = REALTIME_WINDOW_MINUTES
                changed = True
                _LOGGER.warning(
                    "Capped time_window from %s to %d minutes for Trafiklab entry %s (%s); "
                    "multi-request support for longer windows now exists but must be "
                    "re-enabled explicitly since it increases API usage",
                    current_window,
                    REALTIME_WINDOW_MINUTES,
                    entry.entry_id,
                    entry.title,
                )
                ir.async_create_issue(
                    hass,
                    DOMAIN,
                    f"time_window_capped_{entry.entry_id}",
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key="time_window_capped",
                    translation_placeholders={
                        "entry_title": entry.title,
                        "old_value": str(int(current_window)),
                    },
                )

    if original_version < 3:
        hass.config_entries.async_update_entry(
            entry,
            data=data,
            options=options,
            version=3,
        )
        if changed:
            _LOGGER.debug("Migrated Trafiklab entry %s to version 3 (changes applied)", entry.entry_id)
        else:
            _LOGGER.debug("Migrated Trafiklab entry %s to version 3", entry.entry_id)
        return True

    # For already-migrated entries: normalise transport_modes in options in-place
    # without bumping the version, so old-format values don't silently cause
    # "value must be one of [...]" errors in the config / options flow.
    options = dict(entry.options)
    raw_modes = options.get("transport_modes")
    if not isinstance(raw_modes, list):
        options["transport_modes"] = []
        hass.config_entries.async_update_entry(entry, options=options)
        _LOGGER.debug("Normalised transport_modes to [] for entry %s", entry.entry_id)
    elif any(m not in _VALID_TRANSPORT_MODES for m in raw_modes):
        options["transport_modes"] = [m for m in raw_modes if m in _VALID_TRANSPORT_MODES]
        hass.config_entries.async_update_entry(entry, options=options)
        _LOGGER.debug("Removed invalid transport_modes values for entry %s", entry.entry_id)

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
