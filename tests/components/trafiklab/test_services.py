from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import AsyncMock, patch

import pytest
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN, SERVICE_STOP_LOOKUP, SERVICE_UPDATE_NOW, SERVICE_TRAVEL_SEARCH

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


@pytest.mark.asyncio
async def test_stop_lookup_service_returns_stops(hass: Any, setup_integration: bool) -> None:

    mock_api_result = {
        "stop_groups": [
            {
                "id": "g1",
                "name": "Centralen",
                "area_type": "station",
                "transport_modes": ["TRAIN"],
                "average_daily_stop_times": 100,
                "stops": [
                    {"id": "s1", "name": "Centralen A", "lat": 59.0, "lon": 18.0},
                ],
            }
        ]
    }

    with patch("custom_components.trafiklab.api.TrafikLabApiClient.search_stops", return_value=mock_api_result):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_LOOKUP,
            {"api_key": "k", "search_query": "central"},
            blocking=True,
            return_response=True,
        )

    assert response
    assert response.get("total_stops") == 1
    assert response.get("stops_found")[0]["name"] == "Centralen"


@pytest.mark.asyncio
async def test_update_now_all_entries(hass: HomeAssistant) -> None:
    """update_now without config_entry_id refreshes all coordinators."""
    from tests.components.trafiklab.const import ENTRY_DATA_DEPARTURE, ENTRY_OPTIONS_DEFAULT

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_DEPARTURE,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-update-all",
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

    await hass.services.async_call(DOMAIN, SERVICE_UPDATE_NOW, {}, blocking=True)

    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_now_specific_entry(hass: HomeAssistant) -> None:
    """update_now with a valid config_entry_id refreshes only that coordinator."""
    from tests.components.trafiklab.const import ENTRY_DATA_DEPARTURE, ENTRY_OPTIONS_DEFAULT

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_DEPARTURE,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-update-specific",
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

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_NOW,
        {"config_entry_id": entry.entry_id},
        blocking=True,
    )

    coordinator.async_request_refresh.assert_called_once()


@pytest.mark.asyncio
async def test_update_now_invalid_entry_id(hass: HomeAssistant, setup_integration: bool) -> None:
    """update_now with a non-existent entry_id raises ServiceValidationError."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_NOW,
            {"config_entry_id": "does-not-exist"},
            blocking=True,
        )

_RESROBOT_TRIP = {
    "Trip": [
        {
            "LegList": {
                "Leg": [
                    {
                        "Origin": {"name": "Stop A", "date": "2099-12-31", "time": "10:00:00"},
                        "Destination": {"name": "Stop B", "date": "2099-12-31", "time": "10:20:00"},
                        "Product": {"name": "Bus 52", "num": "52"},
                        "category": "BLT",
                        "duration": "PT20M",
                        "direction": "City",
                        "idx": 1,
                    }
                ]
            }
        }
    ]
}


@pytest.mark.asyncio
async def test_travel_search_with_stop_id(hass: Any, setup_integration: bool) -> None:
    """Happy path: travel_search with stop_id origin and destination."""
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "740000001",
                "destination": "740000002",
            },
            blocking=True,
            return_response=True,
        )

    assert response["total_trips"] == 1
    assert len(response["trips"]) == 1
    leg = response["trips"][0]["legs"][0]
    assert leg["origin_name"] == "Stop A"
    assert leg["dest_name"] == "Stop B"
    assert leg["duration"] == 20
    assert "resolved_origin_id" not in response
    assert "resolved_destination_id" not in response


@pytest.mark.asyncio
async def test_travel_search_with_name_resolution(hass: Any, setup_integration: bool) -> None:
    """origin_type='name' and destination_type='name' resolve via search_resrobot_stops."""
    mock_origin_result = {
        "StopLocation": [
            {"extId": "740000001", "name": "Centralen", "lat": "59.330", "lon": "18.059"},
        ]
    }
    mock_dest_result = {
        "StopLocation": [
            {"extId": "740000002", "name": "Odenplan", "lat": "59.342", "lon": "18.049"},
        ]
    }
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.search_resrobot_stops",
        side_effect=[mock_origin_result, mock_dest_result],
    ) as mock_search, patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "Centralen",
                "origin_type": "name",
                "destination": "Odenplan",
                "destination_type": "name",
            },
            blocking=True,
            return_response=True,
        )

    assert mock_search.call_count == 2
    assert mock_trip.call_count == 1
    assert response["resolved_origin_id"] == "740000001"
    assert response["resolved_destination_id"] == "740000002"
    assert response["total_trips"] == 1


@pytest.mark.asyncio
async def test_travel_search_empty_response(hass: Any, setup_integration: bool) -> None:
    """Empty Trip list returns total_trips=0."""
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value={},
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {"api_key": "k", "origin": "740000001", "destination": "740000002"},
            blocking=True,
            return_response=True,
        )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_api_error(hass: Any, setup_integration: bool) -> None:
    """API exception is caught and returned as error field."""
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        side_effect=Exception("network failure"),
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {"api_key": "k", "origin": "740000001", "destination": "740000002"},
            blocking=True,
            return_response=True,
        )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "network failure" in response["error"]


@pytest.mark.asyncio
async def test_travel_search_key_resolved_from_resrobot_entry(hass: HomeAssistant) -> None:
    """Resrobot API key is resolved automatically from a Resrobot config entry."""
    from tests.components.trafiklab.const import ENTRY_DATA_RESROBOT, ENTRY_OPTIONS_DEFAULT

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_RESROBOT,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-keyresolution-resrobot",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {"origin": "740000001", "destination": "740000002"},
            blocking=True,
            return_response=True,
        )

    mock_trip.assert_called_once()
    assert response["total_trips"] == 1
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_no_key_no_entry_returns_error(hass: HomeAssistant, setup_integration: bool) -> None:
    """No api_key and no Resrobot entry returns a descriptive error."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_TRAVEL_SEARCH,
        {"origin": "740000001", "destination": "740000002"},
        blocking=True,
        return_response=True,
    )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "Resrobot API key" in response["error"]


@pytest.mark.asyncio
async def test_stop_lookup_key_resolved_from_departure_entry(hass: HomeAssistant) -> None:
    """Realtime API key is resolved automatically from a departure config entry."""
    from tests.components.trafiklab.const import ENTRY_DATA_DEPARTURE, ENTRY_OPTIONS_DEFAULT

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_DEPARTURE,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-keyresolution-departure",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    mock_api_result = {
        "stop_groups": [
            {
                "id": "g1",
                "name": "Centralen",
                "area_type": "station",
                "transport_modes": ["TRAIN"],
                "average_daily_stop_times": 100,
                "stops": [{"id": "s1", "name": "Centralen A", "lat": 59.0, "lon": 18.0}],
            }
        ]
    }

    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.search_stops",
        return_value=mock_api_result,
    ) as mock_search:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_LOOKUP,
            {"search_query": "central"},
            blocking=True,
            return_response=True,
        )

    mock_search.assert_called_once()
    assert response["total_stops"] == 1
    assert "error" not in response


@pytest.mark.asyncio
async def test_stop_lookup_rejects_unknown_config_entry_id(hass: HomeAssistant, setup_integration: bool) -> None:
    """stop_lookup raises ServiceValidationError for an unknown config_entry_id."""
    with pytest.raises(ServiceValidationError, match="not found"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_LOOKUP,
            {"config_entry_id": "nonexistent-entry-id", "search_query": "central"},
            blocking=True,
            return_response=True,
        )


@pytest.mark.asyncio
async def test_stop_lookup_rejects_resrobot_config_entry_id(hass: HomeAssistant) -> None:
    """stop_lookup raises ServiceValidationError when a Resrobot entry_id is supplied."""
    from tests.components.trafiklab.const import ENTRY_DATA_RESROBOT, ENTRY_OPTIONS_DEFAULT

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=ENTRY_DATA_RESROBOT,
        options=ENTRY_OPTIONS_DEFAULT,
        unique_id="test-stop-lookup-wrong-type",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data",
        return_value={},
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError, match="not a departure or arrival entry"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_LOOKUP,
            {"config_entry_id": entry.entry_id, "search_query": "central"},
            blocking=True,
            return_response=True,
        )


# ---------------------------------------------------------------------------
# Zone and person origin/destination tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_travel_search_with_zone_origin(hass: Any, setup_integration: bool) -> None:
    """origin_type='zone' resolves the zone entity to coordinates."""
    hass.states.async_set(
        "zone.home", "zoning", {"latitude": 59.3293, "longitude": 18.0686}
    )
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "home",
                "origin_type": "zone",
                "destination": "740098000",
            },
            blocking=True,
            return_response=True,
        )

    mock_trip.assert_called_once()
    assert response["resolved_origin_coords"] == "59.3293,18.0686"
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_with_zone_destination(hass: Any, setup_integration: bool) -> None:
    """destination_type='zone' resolves the zone entity to coordinates."""
    hass.states.async_set(
        "zone.work", "zoning", {"latitude": 59.334, "longitude": 18.063}
    )
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "740000001",
                "destination": "Work",
                "destination_type": "zone",
            },
            blocking=True,
            return_response=True,
        )

    assert response["resolved_destination_coords"] == "59.334,18.063"
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_zone_multiword_slugified(hass: Any, setup_integration: bool) -> None:
    """origin_type='zone' with a multi-word name resolves via slugify (e.g. 'My Home' → zone.my_home)."""
    hass.states.async_set(
        "zone.my_home", "zoning", {"latitude": 59.3293, "longitude": 18.0686}
    )
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "My Home",
                "origin_type": "zone",
                "destination": "740098000",
            },
            blocking=True,
            return_response=True,
        )

    mock_trip.assert_called_once()
    assert response["resolved_origin_coords"] == "59.3293,18.0686"
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_zone_by_friendly_name(hass: Any, setup_integration: bool) -> None:
    """origin_type='zone' resolves via friendly_name scan for accented/non-slug names."""
    hass.states.async_set(
        "zone.home", "zoning",
        {"latitude": 59.3293, "longitude": 18.0686, "friendly_name": "Hemma"},
    )
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "Hemma",
                "origin_type": "zone",
                "destination": "740098000",
            },
            blocking=True,
            return_response=True,
        )

    mock_trip.assert_called_once()
    assert response["resolved_origin_coords"] == "59.3293,18.0686"
    assert "error" not in response



    """zone origin that does not exist returns an error field."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_TRAVEL_SEARCH,
        {
            "api_key": "k",
            "origin": "nonexistent_zone",
            "origin_type": "zone",
            "destination": "740098000",
        },
        blocking=True,
        return_response=True,
    )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "nonexistent_zone" in response["error"]


@pytest.mark.asyncio
async def test_travel_search_with_person_gps(hass: Any, setup_integration: bool) -> None:
    """origin_type='person' uses GPS attributes directly."""
    hass.states.async_set(
        "person.john", "home", {"latitude": 59.340, "longitude": 18.055}
    )
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "person.john",
                "origin_type": "person",
                "destination": "740098000",
            },
            blocking=True,
            return_response=True,
        )

    mock_trip.assert_called_once()
    assert response["resolved_origin_coords"] == "59.34,18.055"
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_with_person_zone_fallback(hass: Any, setup_integration: bool) -> None:
    """origin_type='person' falls back to zone coords when no GPS attributes."""
    # Person has no lat/lon — state is "home" which is a zone
    hass.states.async_set("person.jane", "home", {})
    hass.states.async_set(
        "zone.home", "zoning", {"latitude": 59.3293, "longitude": 18.0686}
    )
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "person.jane",
                "origin_type": "person",
                "destination": "740098000",
            },
            blocking=True,
            return_response=True,
        )

    assert response["resolved_origin_coords"] == "59.3293,18.0686"
    assert "error" not in response


@pytest.mark.asyncio
async def test_travel_search_person_no_location(hass: Any, setup_integration: bool) -> None:
    """person entity with no GPS and no matching zone returns an error."""
    hass.states.async_set("person.unknown", "not_home", {})
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_TRAVEL_SEARCH,
        {
            "api_key": "k",
            "origin": "person.unknown",
            "origin_type": "person",
            "destination": "740098000",
        },
        blocking=True,
        return_response=True,
    )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "person.unknown" in response["error"]


# ---------------------------------------------------------------------------
# Coordinate validation tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_travel_search_invalid_origin_coordinates(hass: Any, setup_integration: bool) -> None:
    """origin_type='coordinates' with a malformed value returns a descriptive error."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_TRAVEL_SEARCH,
        {
            "api_key": "k",
            "origin": "not_a_coordinate",
            "origin_type": "coordinates",
            "destination": "740098000",
        },
        blocking=True,
        return_response=True,
    )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "Invalid coordinates for origin" in response["error"]
    assert "not_a_coordinate" in response["error"]


@pytest.mark.asyncio
async def test_travel_search_invalid_destination_coordinates(hass: Any, setup_integration: bool) -> None:
    """destination_type='coordinates' with a malformed value returns a descriptive error."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_TRAVEL_SEARCH,
        {
            "api_key": "k",
            "origin": "740000001",
            "destination": "bad;input",
            "destination_type": "coordinates",
        },
        blocking=True,
        return_response=True,
    )

    assert response["trips"] == []
    assert response["total_trips"] == 0
    assert "Invalid coordinates for destination" in response["error"]
    assert "bad;input" in response["error"]


@pytest.mark.asyncio
async def test_travel_search_valid_coordinates_accepted(hass: Any, setup_integration: bool) -> None:
    """Valid 'lat,lon' coordinates are accepted without error."""
    with patch(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        return_value=_RESROBOT_TRIP,
    ) as mock_trip:
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_TRAVEL_SEARCH,
            {
                "api_key": "k",
                "origin": "59.3293,18.0686",
                "origin_type": "coordinates",
                "destination": "59.334,18.063",
                "destination_type": "coordinates",
            },
            blocking=True,
            return_response=True,
        )

    mock_trip.assert_called_once()
    assert "error" not in response
    assert response["total_trips"] == 1