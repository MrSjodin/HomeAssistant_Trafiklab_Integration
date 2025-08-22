from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN


@pytest.mark.asyncio
async def test_sensor_setup_and_state_departure(hass: HomeAssistant, mock_departures_response) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "key", "stop_id": "740098000", "name": "Test Stop", "sensor_type": "departure"},
        options={"line_filter": "52", "direction": "Central", "time_window": 120, "refresh_interval": 300},
        unique_id="u1",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", return_value=mock_departures_response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Find the created sensor entity by suggested object id pattern
    states = hass.states.async_all("sensor")
    # Expect one sensor
    assert any(s.entity_id.startswith("sensor.trafiklab_departures_") for s in states)

    # Verify attributes structure includes upcoming and attribution
    for s in states:
        if s.entity_id.startswith("sensor.trafiklab_departures_"):
            attrs = s.attributes
            assert "upcoming" in attrs
            assert attrs.get("integration") == DOMAIN
            break


@pytest.mark.asyncio
async def test_sensor_resrobot_shows_minutes_until_and_trips(hass: HomeAssistant, mock_resrobot_response) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "Travel",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 120, "refresh_interval": 300},
        unique_id="u2",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", return_value=mock_resrobot_response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Resrobot sensor entity
    entity = next((s for s in hass.states.async_all("sensor") if s.entity_id.startswith("sensor.trafiklab_travel_")), None)
    assert entity is not None
    # native_value is minutes until next leg within time window (non-negative int or None)
    if entity.state not in ("unknown", "unavailable"):
        assert int(entity.state) >= 0
    attrs = entity.attributes
    assert "trips" in attrs
    assert attrs.get("integration") == DOMAIN
