from unittest.mock import MagicMock

import pytest

from custom_components.trafiklab.api import (
    TrafikLabApiClient,
    TrafikLabNotFoundError,
)


class _MockResponse:
    def __init__(self, status: int, payload: dict) -> None:
        self.status = status
        self.payload = payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def json(self, content_type=None):
        return self.payload

    async def text(self) -> str:
        return ""


@pytest.mark.asyncio
async def test_get_trip_details_uses_trip_path_and_api_key() -> None:
    payload = {"trip": {"trip_id": "trip-123"}, "calls": []}
    session = MagicMock()
    session.get.return_value = _MockResponse(200, payload)
    client = TrafikLabApiClient("test-key", session=session)

    result = await client.get_trip_details("trip-123", "2026-09-26")

    session.get.assert_called_once_with(
        "https://realtime-api.trafiklab.se/v1/trips/trip-123/2026-09-26",
        params={"key": "test-key"},
    )
    assert result == payload


@pytest.mark.asyncio
async def test_get_trip_details_translates_not_found_response() -> None:
    session = MagicMock()
    session.get.return_value = _MockResponse(
        404,
        {"errorCode": "trip.not_found", "errorDetail": "Trip not found"},
    )
    client = TrafikLabApiClient("test-key", session=session)

    with pytest.raises(TrafikLabNotFoundError, match="Trip not found"):
        await client.get_trip_details("missing-trip", "2026-09-26")