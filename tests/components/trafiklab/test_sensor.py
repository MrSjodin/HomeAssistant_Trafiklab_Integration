from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false
import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

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

    # Resolve by unique_id via entity registry
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    unique_id = f"{entry.entry_id}_next_departure"
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", unique_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    attrs = state.attributes
    assert "upcoming" in attrs
    assert attrs.get("integration") == DOMAIN
    # Check friendly name format
    assert state.name == "Test Stop Upcoming Departures"


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

    # Resrobot sensor entity by unique_id
    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    unique_id = f"{entry.entry_id}_resrobot_travel"
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", unique_id)
    assert entity_id is not None
    entity_state = hass.states.get(entity_id)
    assert entity_state is not None
    # Check friendly name format
    assert entity_state.name == "Travel Travel Search"
    # native_value is minutes until next leg within time window (non-negative int or None)
    if entity_state.state not in ("unknown", "unavailable"):
        assert int(entity_state.state) >= 0
    attrs = entity_state.attributes
    assert "trips" in attrs
    assert attrs.get("integration") == DOMAIN
