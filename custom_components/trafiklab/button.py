"""Button platform for Trafiklab — provides an 'Update now' button per config entry."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
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
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_update_now"
        # No suggested_object_id — let HA build the entity_id from device name +
        # entity name (has_entity_name=True), matching the sensor pattern:
        # sensor.avgangar_slussen_kommande_avgangar → button.avgangar_slussen_uppdatera_nu

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info identical to the sensor so the button joins the same device."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": self._entry.data.get(CONF_NAME),
            "manufacturer": "Trafiklab",
            "model": "Public Transport",
        }

    async def async_press(self) -> None:
        """Handle button press — request a debounced coordinator refresh."""
        _LOGGER.debug("[Trafiklab] Update now button pressed for entry %s", self._attr_unique_id)
        await self._coordinator.async_request_refresh()

