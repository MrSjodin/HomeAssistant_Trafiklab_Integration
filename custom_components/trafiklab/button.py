"""Button platform for Trafiklab — provides an 'Update now' button per config entry."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_SENSOR_TYPE,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_RESROBOT,
)
from .coordinator import TrafikLabCoordinator

_LOGGER = logging.getLogger(__name__)


def _slugify(value: str) -> str:
    """Slugify a string for use in entity IDs."""
    v = (value or "").strip().lower()
    v = re.sub(r"\s+", "_", v)
    v = re.sub(r"[^a-z0-9_]", "_", v)
    v = re.sub(r"_+", "_", v)
    return v.strip("_") or "trafiklab"


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

        # Mirror the sensor's suggested_object_id so entity IDs share the same
        # readable prefix, e.g. button.trafiklab_departure_my_stop pairs with
        # sensor.trafiklab_departure_my_stop_next_departure.
        configured_name = (entry.data.get(CONF_NAME) or "").strip() or "trafiklab"
        name_slug = _slugify(configured_name)
        stype = entry.data.get(CONF_SENSOR_TYPE, "departure")
        if stype == SENSOR_TYPE_ARRIVAL:
            self._attr_suggested_object_id = f"trafiklab_arrival_{name_slug}"
        elif stype == SENSOR_TYPE_RESROBOT:
            self._attr_suggested_object_id = f"trafiklab_travel_{name_slug}"
        else:
            self._attr_suggested_object_id = f"trafiklab_departure_{name_slug}"

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

