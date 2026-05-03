"""Button platform for Trafiklab — provides an 'Update now' button per config entry."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import TrafikLabCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Trafiklab update button for this config entry."""
    coordinator: TrafikLabCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TrafikLabUpdateButton(coordinator, entry)])


class TrafikLabUpdateButton(ButtonEntity):
    """Button that triggers an immediate data refresh for a Trafiklab config entry."""

    _attr_has_entity_name = True
    _attr_translation_key = "update_now"

    def __init__(self, coordinator: TrafikLabCoordinator, entry: ConfigEntry) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_update_now"
        self._attr_device_info = None  # no device grouping

    async def async_press(self) -> None:
        """Handle button press — request a debounced coordinator refresh."""
        _LOGGER.debug("[Trafiklab] Update now button pressed for entry %s", self._attr_unique_id)
        await self._coordinator.async_request_refresh()
