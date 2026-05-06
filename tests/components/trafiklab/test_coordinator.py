from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false
import copy
import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

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


# ---------------------------------------------------------------------------
# Platform enrichment tests (CONF_INCLUDE_PLATFORM)
# ---------------------------------------------------------------------------

_PLATFORM_TRIP = {
    "Trip": [
        {
            "LegList": {
                "Leg": [
                    {
                        "type": "JNY",
                        "number": "52",
                        "Origin": {
                            "name": "Stop A",
                            "extId": "740000001",
                            "date": "2025-01-01",
                            "time": "10:00:00",
                        },
                        "Destination": {
                            "name": "Stop B",
                            "date": "2025-01-01",
                            "time": "10:20:00",
                        },
                        "Product": {"name": "Bus 52", "num": "52"},
                        "category": "BLT",
                        "duration": "PT20M",
                    }
                ]
            }
        }
    ]
}

_TIMETABLE_DEPARTURES = {
    "departures": [
        {
            "scheduled": "2025-01-01T10:00:00",
            "realtime_platform": {"designation": "3"},
            "scheduled_platform": {"designation": "3"},
            "route": {"designation": "52"},
        }
    ]
}


@pytest.mark.asyncio
async def test_coordinator_resrobot_platform_enriched(hass: HomeAssistant) -> None:
    """Platform enrichment populates _realtime_platform on legs when include_platform is True."""
    # Departure entry provides the Realtime API key for platform lookup.
    # It must be added AND loaded before the resrobot entry so that the
    # domain is fully initialised and dep_entry appears in hass.data[DOMAIN].
    dep_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "realtime-key",
            "stop_id": "740098000",
            "name": "Dep Sensor",
            "sensor_type": "departure",
        },
        options={},
        unique_id="dep-for-platform",
    )
    dep_entry.add_to_hass(hass)

    # Set up only dep_entry first (this also initialises the domain).
    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data",
        return_value={},
    ):
        await hass.config_entries.async_setup(dep_entry.entry_id)
        await hass.async_block_till_done()

    # Add the resrobot entry AFTER the domain is loaded so HA doesn't try
    # to set it up automatically alongside the departure entry above.
    resrobot_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "resrobot-key",
            "name": "Travel",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 60, "refresh_interval": 300, "include_platform": True},
        unique_id="resrobot-platform",
    )
    resrobot_entry.add_to_hass(hass)

    # Set up resrobot entry with mocked travel search + timetable departures.
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        side_effect=lambda *a, **kw: copy.deepcopy(_PLATFORM_TRIP),
    ), patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        return_value=_TIMETABLE_DEPARTURES,
    ):
        await hass.config_entries.async_setup(resrobot_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][resrobot_entry.entry_id]
    trips = coordinator.data.get("Trip", [])
    assert trips, "Expected at least one trip in coordinator data"
    leg = trips[0]["LegList"]["Leg"][0]
    assert leg.get("_realtime_platform") == "3", (
        f"Expected leg to have _realtime_platform='3', got {leg.get('_realtime_platform')!r}"
    )


@pytest.mark.asyncio
async def test_coordinator_resrobot_platform_no_realtime_key(hass: HomeAssistant) -> None:
    """When include_platform is True but no departure/arrival entry exists, data is returned without crash."""
    # Only a Resrobot entry — no departure/arrival entry to supply the Realtime key
    resrobot_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "resrobot-key",
            "name": "Travel",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 60, "refresh_interval": 300, "include_platform": True},
        unique_id="resrobot-platform-no-key",
    )
    resrobot_entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        side_effect=lambda *a, **kw: copy.deepcopy(_PLATFORM_TRIP),
    ):
        assert await hass.config_entries.async_setup(resrobot_entry.entry_id)
        await hass.async_block_till_done()

    # Data should be present and no exception raised
    coordinator = hass.data[DOMAIN][resrobot_entry.entry_id]
    assert coordinator.data is not None
    trips = coordinator.data.get("Trip", [])
    assert isinstance(trips, list)
    # No platform enrichment should have occurred (no departure entry with Realtime key)
    if trips:
        leg = trips[0]["LegList"]["Leg"][0]
        assert "_realtime_platform" not in leg
