from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN


@pytest.mark.asyncio
async def test_coordinator_respects_update_condition(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={"update_condition": "false"},
        unique_id="u3",
    )
    entry.add_to_hass(hass)

    # If update condition renders false, coordinator should not call API and data remains None/{} without error
    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures") as mocked:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert not mocked.called


@pytest.mark.asyncio
async def test_coordinator_resrobot_normalizes(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "k",
            "name": "T",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "o",
            "destination_type": "stop_id",
            "destination": "d",
        },
        options={"time_window": 60, "refresh_interval": 300},
        unique_id="u4",
    )
    entry.add_to_hass(hass)

    mock_resp = {"Trip": {"LegList": {"Leg": {"Origin": {"date": "2025-01-01", "time": "00:00"}}}}}
    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", return_value=mock_resp):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Coordinator data should have Trip as list
    coordinator = hass.data[DOMAIN][entry.entry_id]
    assert isinstance(coordinator.data.get("Trip"), list)
