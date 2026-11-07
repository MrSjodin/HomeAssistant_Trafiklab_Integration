from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false
import copy
import pytest

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

from unittest.mock import patch, AsyncMock

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
# Time window beyond 60 minutes (multi-call Timetable fetch) tests
# ---------------------------------------------------------------------------

def _departure_item(minutes_from_now: int, designation: str, now) -> dict:
    from datetime import timedelta
    dt_str = (now + timedelta(minutes=minutes_from_now)).strftime("%Y-%m-%dT%H:%M:%S")
    return {
        "scheduled": dt_str,
        "realtime": dt_str,
        "route": {"designation": designation},
        "trip": {"trip_id": f"trip_{designation}", "start_date": "2025-01-01"},
    }


@pytest.mark.asyncio
async def test_coordinator_time_window_60_makes_single_call(hass: HomeAssistant) -> None:
    """The default (and any <=60 minute) time_window must preserve the original single-call behaviour."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={"time_window": 60, "refresh_interval": 300},
        unique_id="u_window_single",
    )
    entry.add_to_hass(hass)

    mock_api = AsyncMock(return_value={"departures": []})
    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", mock_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_api.reset_mock()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_api.call_count == 1
    # The fast path must call with just the stop_id (no explicit "time" argument).
    args, kwargs = mock_api.call_args_list[0]
    assert args == ("740098000",)
    assert kwargs == {}


@pytest.mark.asyncio
async def test_coordinator_time_window_above_60_makes_multiple_calls_and_merges(hass: HomeAssistant) -> None:
    """A time_window above 60 minutes must trigger one Timetable API call per 60-minute chunk,
    merged into a single departures list sorted and trimmed to the configured window."""
    from datetime import datetime

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={"time_window": 150, "refresh_interval": 300},
        unique_id="u_window_multi",
        # Already at the latest version: time_window above 60 is a deliberate, post-migration
        # user choice here, not a legacy value that the v2->v3 migration would cap to 60.
        version=3,
    )
    entry.add_to_hass(hass)

    now = datetime.now()
    # ceil(150 / 60) == 3 chunks: [0,60), [60,120), [120,180) minutes from now.
    responses_by_chunk = {
        0: {"departures": [_departure_item(10, "A", now), _departure_item(50, "B", now)]},
        1: {"departures": [_departure_item(70, "C", now), _departure_item(110, "D", now)]},
        # 140 minutes is within the 150-minute window and must be kept; 170 must be trimmed.
        2: {"departures": [_departure_item(140, "E", now), _departure_item(170, "F", now)]},
    }

    def _side_effect(stop_id, time_str=None):
        # Key the response off the requested chunk's offset rather than call order,
        # since the coordinator issues the per-chunk calls concurrently via asyncio.gather.
        offset_minutes = round((datetime.strptime(time_str, "%Y-%m-%dT%H:%M") - now).total_seconds() / 60)
        chunk_index = round(offset_minutes / 60)
        return responses_by_chunk[chunk_index]

    mock_api = AsyncMock(side_effect=_side_effect)
    with patch("custom_components.trafiklab.api.TrafikLabApiClient.get_departures", mock_api):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        mock_api.reset_mock()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert mock_api.call_count == 3
    departures = coordinator.data.get("departures", [])
    designations = [d["route"]["designation"] for d in departures]
    # "F" (170 min) must be trimmed; the rest must be present, sorted chronologically.
    assert designations == ["A", "B", "C", "D", "E"]


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
            "realtime": "2025-01-01T10:02:30",
            "delay": 150,
            "canceled": False,
            "is_realtime": True,
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
    assert leg.get("_realtime_expected_time") == "2025-01-01 10:02:30"
    assert leg.get("_realtime_delay") == 150
    assert leg.get("_realtime_canceled") is False
    assert leg.get("_is_realtime") is True


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
        assert "_realtime_delay" not in leg


# ---------------------------------------------------------------------------
# Error-handling tests for coordinator
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_coordinator_auth_error_sets_last_api_error_and_repair_issue(hass: HomeAssistant) -> None:
    """TrafikLabAuthError must set last_api_error and create a repair issue."""
    from homeassistant.helpers import issue_registry as ir
    from custom_components.trafiklab.api import TrafikLabAuthError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "bad-key", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={},
        unique_id="coord-auth-err",
    )
    entry.add_to_hass(hass)

    # Setup with a successful mock to avoid ConfigEntryNotReady during first refresh
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        return_value={"departures": []},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.last_api_error = None  # ensure clean state

    # Do exactly one controlled refresh with auth error
    # Note: async_refresh() does not raise — UpdateFailed is handled internally
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        side_effect=TrafikLabAuthError("access denied", http_status=403),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_api_error is not None
    assert coordinator.last_api_error["http_status"] == 403

    issue_reg = ir.async_get(hass)
    issue_id = f"invalid_api_key_{entry.entry_id}"
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is not None


@pytest.mark.asyncio
async def test_coordinator_success_clears_last_api_error_and_repair_issue(hass: HomeAssistant) -> None:
    """A successful update must clear last_api_error and delete any existing repair issue."""
    from homeassistant.helpers import issue_registry as ir
    from custom_components.trafiklab.api import TrafikLabAuthError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "key", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={},
        unique_id="coord-success-clear",
    )
    entry.add_to_hass(hass)

    # Setup with success, then plant the auth error via a controlled refresh
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        return_value={"departures": []},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    # Note: async_refresh() does not raise — UpdateFailed is handled internally
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        side_effect=TrafikLabAuthError("access denied", http_status=403),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Confirm issue was created
    issue_reg = ir.async_get(hass)
    issue_id = f"invalid_api_key_{entry.entry_id}"
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is not None

    # Now succeed — issue and error should be cleared
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        return_value={"departures": []},
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_api_error is None
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.asyncio
async def test_coordinator_quota_error_sets_last_api_error_no_repair_issue(hass: HomeAssistant) -> None:
    """TrafikLabQuotaError must set last_api_error but must NOT create a repair issue."""
    from homeassistant.helpers import issue_registry as ir
    from custom_components.trafiklab.api import TrafikLabQuotaError

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "key", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={},
        unique_id="coord-quota-err",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        return_value={"departures": []},
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.last_api_error = None  # ensure clean state

    # Note: async_refresh() does not raise — UpdateFailed is handled internally
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_departures",
        side_effect=TrafikLabQuotaError("quota exceeded", http_status=429),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.last_api_error is not None
    assert coordinator.last_api_error["http_status"] == 429

    # No repair issue for quota errors
    issue_reg = ir.async_get(hass)
    issue_id = f"invalid_api_key_{entry.entry_id}"
    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None

