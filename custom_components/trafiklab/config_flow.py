"""Config flow for Trafiklab integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import aiohttp

from .const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_SITE_ID,
    CONF_LINE_FILTER,
    CONF_DIRECTION,
    CONF_SENSOR_TYPE,
    CONF_TIME_WINDOW,
    CONF_REFRESH_INTERVAL,
    DEFAULT_NAME,
    DEFAULT_TIME_WINDOW,
    DEFAULT_SCAN_INTERVAL,
    MINIMUM_SCAN_INTERVAL,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_ARRIVAL,
    API_BASE_URL,
    DEPARTURES_ENDPOINT,
    ERROR_API_KEY_INVALID,
    ERROR_STOP_NOT_FOUND,
    ERROR_CONNECTION,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_STOP_ID): str,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)

STEP_SENSOR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR_TYPE, default=SENSOR_TYPE_DEPARTURE): vol.In({
            SENSOR_TYPE_DEPARTURE,
            SENSOR_TYPE_ARRIVAL,
        }),
        vol.Optional(CONF_LINE_FILTER, default=""): str,
        vol.Optional(CONF_DIRECTION, default=""): vol.In({
            "",
            "0",
            "1", 
        }),
        vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1440)
        ),
        vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafiklab."""

    VERSION = 1

    def __init__(self):
        """Initialize config flow."""
        self._api_key = None
        self._stop_id = None
        self._name = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                self._api_key = user_input[CONF_API_KEY]
                self._stop_id = user_input[CONF_STOP_ID]
                self._name = user_input.get(CONF_NAME, DEFAULT_NAME)
                
                # Move to sensor configuration step
                return await self.async_step_sensor()
                
            except CannotConnect:
                errors["base"] = ERROR_CONNECTION
            except InvalidApiKey:
                errors["api_key"] = ERROR_API_KEY_INVALID
            except InvalidStopId:
                errors["stop_id"] = ERROR_STOP_NOT_FOUND
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the sensor configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine all configuration data
            config_data = {
                CONF_API_KEY: self._api_key,
                CONF_STOP_ID: self._stop_id,
                CONF_NAME: self._name,
                CONF_SENSOR_TYPE: user_input[CONF_SENSOR_TYPE],
                CONF_LINE_FILTER: user_input.get(CONF_LINE_FILTER, ""),
                CONF_DIRECTION: user_input.get(CONF_DIRECTION, ""),
                CONF_TIME_WINDOW: user_input.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                CONF_REFRESH_INTERVAL: user_input.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL),
            }

            # Create a unique ID for this sensor configuration
            unique_id = f"{self._stop_id}_{user_input[CONF_SENSOR_TYPE]}"
            if user_input.get(CONF_LINE_FILTER):
                unique_id += f"_{user_input[CONF_LINE_FILTER].replace(',', '_')}"
            if user_input.get(CONF_DIRECTION):
                unique_id += f"_dir{user_input[CONF_DIRECTION]}"

            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Create title with sensor details
            sensor_type_name = "departures" if user_input[CONF_SENSOR_TYPE] == SENSOR_TYPE_DEPARTURE else "arrivals"
            title = f"{self._name} {sensor_type_name}"
            if user_input.get(CONF_LINE_FILTER):
                title += f" (Lines: {user_input[CONF_LINE_FILTER]})"

            return self.async_create_entry(title=title, data=config_data)

        return self.async_show_form(
            step_id="sensor", 
            data_schema=STEP_SENSOR_DATA_SCHEMA, 
            errors=errors,
            description_placeholders={
                "stop_id": self._stop_id,
                "stop_name": self._name,
            }
        )


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    api_key = data[CONF_API_KEY]
    area_id = data[CONF_STOP_ID]

    # Test the API connection
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{API_BASE_URL}{DEPARTURES_ENDPOINT}/{area_id}"
            params = {"key": api_key}
            
            async with session.get(url, params=params) as response:
                if response.status == 401:
                    raise InvalidApiKey
                elif response.status == 404:
                    raise InvalidStopId
                elif response.status != 200:
                    raise CannotConnect
                
                result = await response.json()
                # The new API doesn't use StatusCode, just check if we got valid data
                if "stops" not in result:
                    raise InvalidStopId

    except aiohttp.ClientError as err:
        raise CannotConnect from err

    # Return info that you want to store in the config entry.
    return {"title": data.get(CONF_NAME, DEFAULT_NAME)}


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate there is invalid API key."""


class InvalidStopId(HomeAssistantError):
    """Error to indicate there is invalid stop ID."""
