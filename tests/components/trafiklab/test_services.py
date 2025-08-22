from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from typing import Any

from custom_components.trafiklab.const import DOMAIN, SERVICE_STOP_LOOKUP


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
