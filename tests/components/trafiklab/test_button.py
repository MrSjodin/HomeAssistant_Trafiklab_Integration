"""Tests for the Trafiklab button platform."""
from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN

from tests.components.trafiklab.const import ENTRY_DATA_DEPARTURE, ENTRY_OPTIONS_DEFAULT

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_button_entity_created(hass: HomeAssistant) -> None:
    """A button entity is created for each config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_DEPARTURE,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-button-created",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_update_now")
    assert entity_id is not None


@pytest.mark.asyncio
async def test_button_press_triggers_refresh(hass: HomeAssistant) -> None:
    """Pressing the button calls async_request_refresh on the coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_DEPARTURE,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-button-press",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.async_request_refresh = AsyncMock()

    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("button", DOMAIN, f"{entry.entry_id}_update_now")
    assert entity_id is not None

    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": entity_id},
        blocking=True,
    )

    coordinator.async_request_refresh.assert_called_once()
