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
    RESROBOT_BASE_URL,
    RESROBOT_TRAVEL_SEARCH_ENDPOINT,
    RESROBOT_LOCATION_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------

class TrafikLabApiError(Exception):
    """Base exception for all Trafiklab API errors."""

    def __init__(
        self,
        message: str = "",
        *,
        error_code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.http_status = http_status


class TrafikLabAuthError(TrafikLabApiError):
    """Raised when authentication fails (invalid / missing API key)."""


class TrafikLabQuotaError(TrafikLabApiError):
    """Raised when the API quota or rate limit is exceeded."""


class TrafikLabNotFoundError(TrafikLabApiError):
    """Raised when a stop / resource is not found."""


class TrafikLabServerError(TrafikLabApiError):
    """Raised when the API returns a server-side error (5xx)."""


# ---------------------------------------------------------------------------
# Private error-parsing helpers
# ---------------------------------------------------------------------------

def _raise_realtime_error(
    status: int, body_text: str, json_body: dict | None
) -> None:
    """Parse a non-2xx Realtime API response and raise the appropriate exception.

    Realtime error format (HTTP 403 example):
        {"errorCode": "error.key.invalid", "errorDetail": "Key '...' does not exist.", "parameterValues": []}
    """
    error_code: str = ""
    error_detail: str = ""
    if json_body:
        error_code = (json_body.get("errorCode") or "").lower()
        error_detail = json_body.get("errorDetail") or json_body.get("message") or ""

    message = error_detail or body_text or f"HTTP {status}"

    # Auth: explicit error code patterns OR 401/403
    if (
        "key" in error_code
        or "auth" in error_code
        or "unauthorized" in error_code
        or status in (401, 403)
    ):
        raise TrafikLabAuthError(message, error_code=error_code or None, http_status=status)

    # Quota / rate-limit
    if "quota" in error_code or "rate" in error_code or "limit" in error_code or status == 429:
        raise TrafikLabQuotaError(message, error_code=error_code or None, http_status=status)

    # Not found: explicit code or 404
    if "not_found" in error_code or "stop" in error_code or "location" in error_code or status == 404:
        raise TrafikLabNotFoundError(message, error_code=error_code or None, http_status=status)

    # Server errors
    if status >= 500:
        raise TrafikLabServerError(message, error_code=error_code or None, http_status=status)

    # Catch-all
    raise TrafikLabApiError(message, error_code=error_code or None, http_status=status)


def _raise_resrobot_error(
    status: int, body_text: str, json_body: dict | None
) -> None:
    """Parse a non-2xx Resrobot API response and raise the appropriate exception.

    Resrobot error format:
        {"errorCode": "API_AUTH", "errorText": "access denied for ...", ...}

    SVC_NO_RESULT (HTTP 200) is handled upstream as an empty Trip list, not here.
    """
    error_code: str = ""
    error_text: str = ""
    if json_body:
        error_code = (json_body.get("errorCode") or "").upper()
        error_text = json_body.get("errorText") or json_body.get("errorDetail") or ""

    message = error_text or body_text or f"HTTP {status}"

    # Auth errors
    if error_code == "API_AUTH" or status in (401, 403):
        raise TrafikLabAuthError(message, error_code=error_code or None, http_status=status)

    # Quota / rate-limit
    if error_code in ("API_QUOTA", "API_TOO_MANY_REQUESTS") or status == 429:
        raise TrafikLabQuotaError(message, error_code=error_code or None, http_status=status)

    # Location / not-found type errors
    if error_code.startswith("SVC_LOC") or error_code == "SVC_NO_MATCH" or status == 404:
        raise TrafikLabNotFoundError(message, error_code=error_code or None, http_status=status)

    # Server errors
    if error_code.startswith("INT_") or status >= 500:
        raise TrafikLabServerError(message, error_code=error_code or None, http_status=status)

    # Catch-all (bad request etc.)
    raise TrafikLabApiError(message, error_code=error_code or None, http_status=status)


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class TrafikLabApiClient:
    """API client for Trafiklab and Resrobot endpoints."""
    async def get_resrobot_travel_search(
        self,
        api_key: str,
        origin_type: str,
        origin: str,
        destination_type: str,
        destination: str,
        via: str = "",
        avoid: str = "",
        max_walking_distance: int = 1000,
        products: int | None = None,
    ) -> dict[str, Any]:
        """Call Resrobot Travel Search API."""
        # Build endpoint and params
        url = f"{RESROBOT_BASE_URL}{RESROBOT_TRAVEL_SEARCH_ENDPOINT}"
        params = {
            "accessId": api_key,
            "format": "json",
        }
        # Origin
        if origin_type == "stop_id":
            params["originId"] = origin
        else:
            lat, lon = origin.split(",")
            params["originCoordLat"] = lat.strip()
            params["originCoordLong"] = lon.strip()
        # Destination
        if destination_type == "stop_id":
            params["destId"] = destination
        else:
            lat, lon = destination.split(",")
            params["destCoordLat"] = lat.strip()
            params["destCoordLong"] = lon.strip()
        # Optional
        if via:
            params["viaId"] = via
        if avoid:
            params["avoidId"] = avoid
        # Walking distance (originWalk and destWalk)
        # API expects: allowWalk, minDistance, maxDistance, percent
        params["originWalk"] = f"1,0,{max_walking_distance},75"
        params["destWalk"] = f"1,0,{max_walking_distance},75"
        # Transport mode / products bitmask filter (request-side)
        if products is not None:
            params["products"] = str(products)

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                response_text = await response.text()
                json_body: dict | None = None
                try:
                    json_body = await response.json(content_type=None)
                except Exception:
                    pass
                _raise_resrobot_error(response.status, response_text, json_body)
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Resrobot request timed out") from err
        except TrafikLabApiError:
            raise
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Resrobot request failed: {err}") from err
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
                if response.status == 200:
                    return await response.json()

                response_text = await response.text()
                json_body: dict | None = None
                try:
                    json_body = await response.json(content_type=None)
                except Exception:
                    pass
                _raise_realtime_error(response.status, response_text, json_body)

        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Request timed out") from err
        except TrafikLabApiError:
            raise
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
                if response.status == 200:
                    return await response.json()
                response_text = await response.text()
                json_body: dict | None = None
                try:
                    json_body = await response.json(content_type=None)
                except Exception:
                    pass
                _raise_realtime_error(response.status, response_text, json_body)
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Request timed out") from err
        except TrafikLabApiError:
            raise
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Request failed: {err}") from err

    async def search_stops(self, search_value: str) -> dict[str, Any]:
        """Search for stops by name using the Realtime API (returns local stop IDs)."""
        url = f"{API_BASE_URL}{STOP_LOOKUP_ENDPOINT}/{search_value}"
        params = {"key": self.api_key}

        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                response_text = await response.text()
                json_body: dict | None = None
                try:
                    json_body = await response.json(content_type=None)
                except Exception:
                    pass
                _raise_realtime_error(response.status, response_text, json_body)
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Request timed out") from err
        except TrafikLabApiError:
            raise
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Request failed: {err}") from err

    async def search_resrobot_stops(self, search_value: str, api_key: str) -> dict[str, Any]:
        """Search for stops by name using Resrobot /location.name (returns national stop IDs).

        Use this when the resolved stop ID will be passed to get_resrobot_travel_search.
        Returns a dict with a ``StopLocation`` list, each entry having an ``extId``
        field containing the national 9-digit stop ID (e.g. "740000001").
        """
        url = f"{RESROBOT_BASE_URL}{RESROBOT_LOCATION_ENDPOINT}"
        params = {
            "accessId": api_key,
            "input": search_value,
            "format": "json",
        }
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    _LOGGER.debug("Resrobot location.name raw response for %r: %s", search_value, data)
                    return data
                response_text = await response.text()
                json_body: dict | None = None
                try:
                    json_body = await response.json(content_type=None)
                except Exception:
                    pass
                _raise_resrobot_error(response.status, response_text, json_body)
        except asyncio.TimeoutError as err:
            raise TrafikLabApiError("Resrobot location lookup timed out") from err
        except TrafikLabApiError:
            raise
        except aiohttp.ClientError as err:
            raise TrafikLabApiError(f"Resrobot location lookup failed: {err}") from err

    async def validate_api_key(self, area_id: str = "740098000") -> bool:
        """Validate the API key by making a test request to Stockholm."""
        try:
            await self.get_departures(area_id)
            return True
        except TrafikLabApiError:
            return False
