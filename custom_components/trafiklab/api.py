"""Trafiklab API client."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL, 
    DEPARTURES_ENDPOINT, 
    ARRIVALS_ENDPOINT,
    STOP_LOOKUP_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


class TrafikLabApiClient:
    """API client for Trafiklab."""

    def __init__(self, api_key: str, session: aiohttp.ClientSession | None = None, timeout: int = 15) -> None:
        """Initialize the API client."""
        self.api_key = api_key
        self._session = session
        self._close_session = False
        self.timeout = timeout

    async def __aenter__(self) -> TrafikLabApiClient:
        """Async context manager entry."""
        return self

    async def __aexit__(self, *args) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the session if we created it."""
        if self._close_session and self._session:
            await self._session.close()

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create session."""
        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)
            self._close_session = True
        return self._session

    async def get_departures(
        self,
        area_id: str,
        time: str | None = None,
    ) -> dict[str, Any]:
        """Get departures for an area."""
        if time:
            url = f"{API_BASE_URL}{DEPARTURES_ENDPOINT}/{area_id}/{time}"
        else:
            url = f"{API_BASE_URL}{DEPARTURES_ENDPOINT}/{area_id}"
        
        params = {"key": self.api_key}

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Request failed: {err}") from err

    async def get_arrivals(
        self,
        area_id: str,
        time: str | None = None,
    ) -> dict[str, Any]:
        """Get arrivals for an area."""
        if time:
            url = f"{API_BASE_URL}{ARRIVALS_ENDPOINT}/{area_id}/{time}"
        else:
            url = f"{API_BASE_URL}{ARRIVALS_ENDPOINT}/{area_id}"
        
        params = {"key": self.api_key}

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Request failed: {err}") from err

    async def search_stops(self, search_value: str) -> dict[str, Any]:
        """Search for stops by name."""
        url = f"{API_BASE_URL}{STOP_LOOKUP_ENDPOINT}/{search_value}"
        params = {"key": self.api_key}

        try:
            async with self.session.get(url, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Request timed out") from err
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Request failed: {err}") from err

    async def validate_api_key(self, area_id: str = "740098000") -> bool:
        """Validate the API key by making a test request to Stockholm."""
        try:
            await self.get_departures(area_id)
            return True
        except TrafikLabApiError:
            return False


class TrafikLabApiError(Exception):
    """Exception for Trafiklab API errors."""
