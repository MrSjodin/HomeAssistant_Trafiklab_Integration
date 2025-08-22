from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from typing import Any
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN, SERVICE_STOP_LOOKUP


@pytest.mark.asyncio
async def test_async_setup_registers_service(hass: Any, setup_integration: bool) -> None:
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_LOOKUP)


@pytest.mark.asyncio
async def test_setup_entry_and_unload_removes_services_when_last_entry(hass: Any, enable_custom_integrations: None) -> None:
    # Ensure domain is set up so services register
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})

    # Mock API calls used by coordinator during first refresh
    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", return_value={
        "timestamp": "2025-01-01T12:00:00+00:00",
        "query": {},
        "stops": [],
        "departures": [],
    }):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
            options={},
            unique_id="u1",
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Service should be present
        assert hass.services.has_service(DOMAIN, SERVICE_STOP_LOOKUP)

        # Unload the only entry -> services should be removed
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()

        assert not hass.services.has_service(DOMAIN, SERVICE_STOP_LOOKUP)
