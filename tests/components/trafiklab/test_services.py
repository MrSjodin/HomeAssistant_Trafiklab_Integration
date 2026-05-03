from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import AsyncMock, patch

import pytest
from typing import Any

from homeassistant.exceptions import ServiceValidationError
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN, SERVICE_STOP_LOOKUP, SERVICE_UPDATE_NOW

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
