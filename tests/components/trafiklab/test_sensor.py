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


# ---------------------------------------------------------------------------
# Tests for transport_modes filter (Realtime / departure sensor)
# ---------------------------------------------------------------------------

def _make_departure_item(designation: str, transport_mode: str, direction: str = "Centrum") -> dict:
    """Build a minimal departure item for testing."""
    from datetime import datetime, timedelta
    future = (datetime.now() + timedelta(minutes=10)).isoformat()
    return {
        "scheduled": future,
        "realtime": future,
        "is_realtime": True,
        "delay": 0,
        "canceled": False,
        "realtime_platform": {"designation": "A"},
        "scheduled_platform": {"designation": "A"},
        "route": {
            "designation": designation,
            "direction": direction,
            "transport_mode": transport_mode,
            "name": f"Line {designation}",
        },
        "agency": {"name": "SL"},
        "trip": {"trip_id": f"trip_{designation}"},
    }


@pytest.mark.asyncio
async def test_departure_sensor_filters_by_transport_mode(hass: HomeAssistant) -> None:
    """Items whose transport_mode is not in transport_modes must be excluded."""
    bus_item = _make_departure_item("52", "BUS")
    metro_item = _make_departure_item("T14", "METRO")
    mock_response = {"departures": [bus_item, metro_item]}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "key", "stop_id": "740098000", "name": "ModeTest", "sensor_type": "departure"},
        options={"transport_modes": ["bus"], "time_window": 120, "refresh_interval": 300},
        unique_id="mode_filter_bus",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", return_value=mock_response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_next_departure")
    assert entity_id is not None
    attrs = hass.states.get(entity_id).attributes
    upcoming = attrs.get("upcoming", [])
    # Only the BUS item should appear
    assert len(upcoming) == 1
    assert upcoming[0]["transport_mode"].upper() == "BUS"


@pytest.mark.asyncio
async def test_departure_sensor_empty_transport_modes_returns_all(hass: HomeAssistant) -> None:
    """When transport_modes is empty, all items must be returned regardless of mode."""
    bus_item = _make_departure_item("52", "BUS")
    metro_item = _make_departure_item("T14", "METRO")
    tram_item = _make_departure_item("7", "TRAM")
    mock_response = {"departures": [bus_item, metro_item, tram_item]}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "key", "stop_id": "740098000", "name": "AllModes", "sensor_type": "departure"},
        options={"transport_modes": [], "time_window": 120, "refresh_interval": 300},
        unique_id="mode_filter_all",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", return_value=mock_response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_next_departure")
    assert entity_id is not None
    attrs = hass.states.get(entity_id).attributes
    assert len(attrs.get("upcoming", [])) == 3


@pytest.mark.asyncio
async def test_departure_sensor_absent_transport_modes_key_returns_all(hass: HomeAssistant) -> None:
    """Legacy entries without transport_modes key must not be filtered (backward compat)."""
    bus_item = _make_departure_item("52", "BUS")
    train_item = _make_departure_item("40", "TRAIN")
    mock_response = {"departures": [bus_item, train_item]}

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "key", "stop_id": "740098000", "name": "Legacy", "sensor_type": "departure"},
        options={"time_window": 120, "refresh_interval": 300},  # no transport_modes key
        unique_id="mode_filter_legacy",
    )
    entry.add_to_hass(hass)

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", return_value=mock_response):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_next_departure")
    attrs = hass.states.get(entity_id).attributes
    assert len(attrs.get("upcoming", [])) == 2


# ---------------------------------------------------------------------------
# Tests for products bitmask passed to Resrobot API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resrobot_multi_mode_makes_separate_api_calls(hass: HomeAssistant, mock_resrobot_response) -> None:
    """When multiple transport_modes are set, one API call per mode must be made (not a combined bitmask)."""
    from unittest.mock import AsyncMock, patch as _patch
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "BikeRide",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 120, "refresh_interval": 300, "transport_modes": ["metro", "train"]},
        unique_id="resrobot_products_test",
    )
    entry.add_to_hass(hass)

    mock_api = AsyncMock(return_value=mock_resrobot_response)
    with _patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", mock_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Reset after setup (HA may trigger more than one refresh during entry setup)
        mock_api.reset_mock()

        # Trigger exactly one coordinator refresh and count the resulting API calls
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Two modes → two separate API calls, one with products=32 (METRO) and one with products=22 (TRAIN)
    assert mock_api.call_count == 2
    products_passed = {
        (kwargs.get("products") if "products" in kwargs else (args[-1] if args else None))
        for args, kwargs in mock_api.call_args_list
    }
    assert products_passed == {32, 22}  # METRO=32, TRAIN=22 each called separately


@pytest.mark.asyncio
async def test_resrobot_single_mode_makes_one_api_call(hass: HomeAssistant, mock_resrobot_response) -> None:
    """When a single transport_mode is set, exactly one API call is made."""
    from unittest.mock import AsyncMock, patch as _patch
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "SingleMode",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 120, "refresh_interval": 300, "transport_modes": ["bus"]},
        unique_id="resrobot_single_mode_test",
    )
    entry.add_to_hass(hass)

    mock_api = AsyncMock(return_value=mock_resrobot_response)
    with _patch("custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search", mock_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # Reset after setup (HA may trigger more than one refresh during entry setup)
        mock_api.reset_mock()

        # Trigger exactly one coordinator refresh and count the resulting API calls
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_api.call_count == 1
    args, kwargs = mock_api.call_args
    products_passed = kwargs.get("products") if "products" in kwargs else (args[-1] if args else None)
    assert products_passed == 136  # BUS=136


@pytest.mark.asyncio
async def test_resrobot_multi_mode_merges_and_deduplicates_trips(hass: HomeAssistant) -> None:
    """Multi-mode calls must merge trips from all responses and deduplicate identical trips."""
    from unittest.mock import AsyncMock, patch as _patch

    metro_trip = {
        "LegList": {
            "Leg": [
                {
                    "Origin": {"name": "Stop A", "date": "2099-12-31", "time": "10:00:00"},
                    "Destination": {"name": "Stop B", "date": "2099-12-31", "time": "10:20:00"},
                    "Product": {"name": "T-bana 13"},
                    "category": "ULT",
                    "duration": "PT20M",
                    "direction": "Central",
                    "idx": 1,
                }
            ]
        }
    }
    bus_trip = {
        "LegList": {
            "Leg": [
                {
                    "Origin": {"name": "Stop A", "date": "2099-12-31", "time": "10:05:00"},
                    "Destination": {"name": "Stop B", "date": "2099-12-31", "time": "10:45:00"},
                    "Product": {"name": "Bus 4"},
                    "category": "BLT",
                    "duration": "PT40M",
                    "direction": "Central",
                    "idx": 1,
                }
            ]
        }
    }

    # METRO response contains only metro_trip; BUS response contains only bus_trip
    metro_response = {"Trip": [metro_trip]}
    bus_response = {"Trip": [bus_trip]}

    call_count = 0
    async def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        products = kwargs.get("products") if "products" in kwargs else (args[-1] if args else None)
        if products == 32:   # METRO
            return metro_response
        return bus_response  # BUS

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "key",
            "name": "MultiMerge",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 99999, "refresh_interval": 300, "transport_modes": ["metro", "bus"]},
        unique_id="resrobot_merge_test",
    )
    entry.add_to_hass(hass)

    with _patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        side_effect=side_effect,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er
    ent_reg = er.async_get(hass)
    entity_id = ent_reg.async_get_entity_id("sensor", "trafiklab", f"{entry.entry_id}_resrobot_travel")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    trips = state.attributes.get("trips", [])
    # Both Metro and Bus trips must appear in the merged result
    assert len(trips) == 2
    categories = {leg["category"] for trip in trips for leg in trip.get("legs", [])}
    assert "Metro" in categories
    assert "Bus" in categories
