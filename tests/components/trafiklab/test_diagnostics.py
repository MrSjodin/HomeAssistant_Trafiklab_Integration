from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN
from custom_components.trafiklab import diagnostics as diag


@pytest.mark.asyncio
async def test_diagnostics_redacts_api_key(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "secret", "stop_id": "740098000", "name": "Test Stop", "sensor_type": "departure"},
        options={},
        unique_id="u1",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", return_value={
        "timestamp": "2025-01-01T12:00:00+00:00",
        "query": {},
        "stops": [],
        "departures": [],
    }):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    data = await diag.async_get_config_entry_diagnostics(hass, entry)
    # Confirm secret is redacted by diagnostics helper (HA uses 'REDACTED')
    assert data["config_entry"]["data"]["api_key"] == "REDACTED"
    # Should include coordinator keys
    assert "coordinator" in data
