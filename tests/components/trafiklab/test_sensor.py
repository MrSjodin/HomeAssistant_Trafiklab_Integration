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


# ---------------------------------------------------------------------------
# Tests for max_trip_duration and duration_total
# ---------------------------------------------------------------------------

def _make_resrobot_response_with_duration(dep_time: str, arr_time: str, date: str = "2099-12-31") -> dict:
    """Build a minimal single-trip ResRobot response with configurable dep/arr times."""
    return {
        "Trip": [
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "Stop A", "date": date, "time": dep_time},
                            "Destination": {"name": "Stop B", "date": date, "time": arr_time},
                            "Product": {"name": "Bus 52", "num": "52"},
                            "category": "BUS",
                            "duration": "PT20M",
                            "direction": "Central Station",
                            "idx": 1,
                        }
                    ]
                }
            }
        ]
    }


@pytest.mark.asyncio
async def test_resrobot_duration_total_in_attributes(hass: HomeAssistant) -> None:
    """duration_total must be present in every trip entry in sensor attributes."""
    # Trip runs 12:00 → 12:45 = 45 minutes
    mock_resp = _make_resrobot_response_with_duration("12:00:00", "12:45:00")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "DurTest",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 9999, "refresh_interval": 300},
        unique_id="dur_total_test",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", return_value=mock_resp):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_resrobot_travel")
    assert entity_id is not None
    attrs = hass.states.get(entity_id).attributes
    assert "trips" in attrs
    trips = attrs["trips"]
    assert len(trips) == 1
    assert "duration_total" in trips[0]
    assert trips[0]["duration_total"] == 45


@pytest.mark.asyncio
async def test_resrobot_max_trip_duration_filters_long_trips(hass: HomeAssistant) -> None:
    """Trips exceeding max_trip_duration must not appear in sensor attributes."""
    # Two trips: 20 min and 90 min. With max_trip_duration=30 only the 20-min trip survives.
    mock_resp = {
        "Trip": [
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "Stop A", "date": "2099-12-31", "time": "12:00:00"},
                            "Destination": {"name": "Stop B", "date": "2099-12-31", "time": "12:20:00"},
                            "Product": {"name": "Bus 1", "num": "1"},
                            "category": "BUS",
                            "duration": "PT20M",
                            "direction": "North",
                            "idx": 1,
                        }
                    ]
                }
            },
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "Stop A", "date": "2099-12-31", "time": "13:00:00"},
                            "Destination": {"name": "Stop C", "date": "2099-12-31", "time": "14:30:00"},
                            "Product": {"name": "Train 2", "num": "2"},
                            "category": "TRN",
                            "duration": "PT1H30M",
                            "direction": "South",
                            "idx": 1,
                        }
                    ]
                }
            },
        ]
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "FilterTest",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000010",
            "destination_type": "stop_id",
            "destination": "740000020",
        },
        options={"time_window": 9999, "refresh_interval": 300, "max_trip_duration": 30},
        unique_id="max_dur_filter_test",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", return_value=mock_resp):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_resrobot_travel")
    assert entity_id is not None
    attrs = hass.states.get(entity_id).attributes
    trips = attrs.get("trips", [])
    # Only the 20-minute trip should remain
    assert len(trips) == 1
    assert trips[0]["duration_total"] == 20


@pytest.mark.asyncio
async def test_resrobot_no_max_trip_duration_key_returns_all_trips(hass: HomeAssistant) -> None:
    """When max_trip_duration key is absent (old config entry), all trips are returned."""
    mock_resp = {
        "Trip": [
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "Stop A", "date": "2099-12-31", "time": "12:00:00"},
                            "Destination": {"name": "Stop B", "date": "2099-12-31", "time": "14:00:00"},
                            "Product": {"name": "Train 1", "num": "1"},
                            "category": "TRN",
                            "duration": "PT2H",
                            "direction": "East",
                            "idx": 1,
                        }
                    ]
                }
            }
        ]
    }
    # Simulate a legacy entry: options dict has NO max_trip_duration key at all
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "LegacyTest",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000030",
            "destination_type": "stop_id",
            "destination": "740000040",
        },
        options={"time_window": 9999, "refresh_interval": 300},  # no max_trip_duration key
        unique_id="legacy_no_max_dur",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", return_value=mock_resp):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_resrobot_travel")
    assert entity_id is not None
    attrs = hass.states.get(entity_id).attributes
    trips = attrs.get("trips", [])
    # All trips must be present — 120-minute trip not filtered
    assert len(trips) == 1
    assert trips[0]["duration_total"] == 120


@pytest.mark.asyncio
async def test_resrobot_max_trip_duration_none_returns_all_trips(hass: HomeAssistant) -> None:
    """When max_trip_duration is explicitly None, all trips are returned (no limit)."""
    mock_resp = _make_resrobot_response_with_duration("12:00:00", "15:00:00")  # 180 min
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "NullTest",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000050",
            "destination_type": "stop_id",
            "destination": "740000060",
        },
        options={"time_window": 9999, "refresh_interval": 300, "max_trip_duration": None},
        unique_id="null_max_dur",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", return_value=mock_resp):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_resrobot_travel")
    assert entity_id is not None
    attrs = hass.states.get(entity_id).attributes
    trips = attrs.get("trips", [])
    assert len(trips) == 1
    assert trips[0]["duration_total"] == 180
