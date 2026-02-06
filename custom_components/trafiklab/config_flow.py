"""Config flow for Trafiklab integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME as HA_CONF_NAME  # avoid collision; not used
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import TrafikLabApiClient, TrafikLabApiError

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_SITE_ID,
    CONF_LINE_FILTER,
    CONF_DIRECTION,
    CONF_SENSOR_TYPE,
    CONF_TIME_WINDOW,
    CONF_REFRESH_INTERVAL,
    CONF_UPDATE_CONDITION,
    DEFAULT_NAME,
    DEFAULT_TIME_WINDOW,
    DEFAULT_SCAN_INTERVAL,
    MINIMUM_SCAN_INTERVAL,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_RESROBOT,
    API_BASE_URL,
    DEPARTURES_ENDPOINT,
    ERROR_API_KEY_INVALID,
    ERROR_STOP_NOT_FOUND,
    ERROR_CONNECTION,
    CONF_ORIGIN_TYPE,
    CONF_ORIGIN,
    CONF_DESTINATION_TYPE,
    CONF_DESTINATION,
    CONF_VIA,
    CONF_AVOID,
    CONF_MAX_WALKING_DISTANCE,
)

_LOGGER = logging.getLogger(__name__)


def _default_name_for_type(lang: str, sensor_type: str) -> str:
    lang = (lang or "en").lower()
    is_sv = lang.startswith("sv")
    if sensor_type == SENSOR_TYPE_DEPARTURE:
        return "Avgångar" if is_sv else "Departures"
    if sensor_type == SENSOR_TYPE_ARRIVAL:
        return "Ankomster" if is_sv else "Arrivals"
    # SENSOR_TYPE_RESROBOT
    return "Resesökning" if is_sv else "Travel Search"

STEP_SENSOR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR_TYPE, default=SENSOR_TYPE_DEPARTURE): vol.In({
            SENSOR_TYPE_DEPARTURE,
            SENSOR_TYPE_ARRIVAL,
        }),
        vol.Optional(CONF_LINE_FILTER, default=""): str,
    # Direction is now a free text destination filter (substring match). Keep key name for backward compatibility.
    vol.Optional(CONF_DIRECTION, default=""): str,
        vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=1440)
        ),
        vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
        ),
    # New: Optional Jinja template string to decide whether to perform update. When template renders to 'true' (case-insensitive), update is performed.
    vol.Optional(CONF_UPDATE_CONDITION, default=""): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafiklab."""

    VERSION = 2


    def __init__(self):
        """Initialize config flow."""
        self._api_key = None
        self._stop_id = None
        self._name = None
        self._sensor_type = None


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: sensor type and API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
                # Legacy path: allow initial form to accept api_key + stop_id (+ name)
                if CONF_STOP_ID in user_input and CONF_API_KEY in user_input and CONF_SENSOR_TYPE not in user_input:
                    self._api_key = user_input[CONF_API_KEY]
                    self._stop_id = user_input[CONF_STOP_ID]
                    self._name = user_input.get(CONF_NAME, DEFAULT_NAME)
                    try:
                        await validate_input(self.hass, {
                            CONF_API_KEY: self._api_key,
                            CONF_STOP_ID: self._stop_id,
                        })
                    except InvalidApiKey:
                        errors["api_key"] = "invalid_api_key"
                    except InvalidStopId:
                        errors["stop_id"] = "invalid_stop_id"
                    except CannotConnect:
                        errors["base"] = "cannot_connect"
                    except Exception as err:  # pragma: no cover
                        _LOGGER.exception("Unexpected exception during validation: %s", err)
                        errors["base"] = "unknown"
                    else:
                        # Proceed to sensor configuration step
                        return await self.async_step_sensor()
                else:
                    # New path: choose sensor type first
                    self._sensor_type = user_input[CONF_SENSOR_TYPE]
                    self._api_key = user_input[CONF_API_KEY]
                    # Use user-provided name or a default based on type + language
                    default_name = _default_name_for_type(getattr(self.hass.config, "language", "en"), self._sensor_type)
                    self._name = (user_input.get(CONF_NAME) or default_name)
                    # Next step depends on sensor type
                    if self._sensor_type in [SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL]:
                        return await self.async_step_departure_arrival()
                    elif self._sensor_type == SENSOR_TYPE_RESROBOT:
                        return await self.async_step_resrobot()

        # Show initial form with dynamic default name based on default sensor type
        default_type = SENSOR_TYPE_RESROBOT
        lang = getattr(self.hass.config, "language", "en")
        default_name = _default_name_for_type(lang, default_type)
        dynamic_schema = vol.Schema(
            {
                vol.Required(CONF_SENSOR_TYPE, default=default_type): vol.In({
                    SENSOR_TYPE_RESROBOT,
                    SENSOR_TYPE_DEPARTURE,
                    SENSOR_TYPE_ARRIVAL,
                }),
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=default_name): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=dynamic_schema,
            errors=errors,
        )

    async def async_step_departure_arrival(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for Departure/Arrival sensor config."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._stop_id = user_input[CONF_STOP_ID]
            # Validate input as before
            try:
                await validate_input(self.hass, {
                    CONF_API_KEY: self._api_key,
                    CONF_STOP_ID: self._stop_id,
                })
            except InvalidApiKey:
                errors["api_key"] = "invalid_api_key"
            except InvalidStopId:
                errors["stop_id"] = "invalid_stop_id"
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected exception during validation: %s", err)
                errors["base"] = "unknown"
            else:
                # Combine config data
                base_data = {
                    CONF_API_KEY: self._api_key,
                    CONF_STOP_ID: self._stop_id,
                    CONF_NAME: self._name,
                    CONF_SENSOR_TYPE: self._sensor_type,
                }
                options_data = {
                    CONF_LINE_FILTER: user_input.get(CONF_LINE_FILTER, ""),
                    CONF_DIRECTION: user_input.get(CONF_DIRECTION, ""),
                    CONF_TIME_WINDOW: user_input.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                    CONF_REFRESH_INTERVAL: user_input.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_UPDATE_CONDITION: user_input.get(CONF_UPDATE_CONDITION, ""),
                }
                unique_id = f"{self._stop_id}_{self._sensor_type}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                sensor_type_name = "Departures" if self._sensor_type == SENSOR_TYPE_DEPARTURE else "Arrivals"
                title = f"{self._name} {sensor_type_name}"
                return self.async_create_entry(title=title, data=base_data, options=options_data)

        # Show form for Departure/Arrival sensor config
        return self.async_show_form(
            step_id="departure_arrival",
            data_schema=vol.Schema({
                vol.Required(CONF_STOP_ID): str,
                vol.Optional(CONF_LINE_FILTER, default=""): str,
                vol.Optional(CONF_DIRECTION, default=""): str,
                vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=1440)
                ),
                vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
                ),
                vol.Optional(CONF_UPDATE_CONDITION, default=""): str,
            }),
            errors=errors,
        )

    async def async_step_resrobot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for Resrobot Travel Search sensor config."""
        errors: dict[str, str] = {}

        # Define all required fields for Resrobot, including update frequency and time window
        # Keep options simple; labels are translated via step strings
        resrobot_schema = vol.Schema({
            vol.Required(CONF_ORIGIN_TYPE, default="stop_id"): vol.In(["stop_id", "coordinates"]),
            vol.Required(CONF_ORIGIN, default=""): str,
            vol.Required(CONF_DESTINATION_TYPE, default="stop_id"): vol.In(["stop_id", "coordinates"]),
            vol.Required(CONF_DESTINATION, default=""): str,
            vol.Optional(CONF_VIA, default=""): str,
            vol.Optional(CONF_AVOID, default=""): str,
            vol.Optional(CONF_MAX_WALKING_DISTANCE, default=1000): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
            vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)),
            vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        })

        if user_input is not None:
            # Validate origin/destination types and values
            origin_type = user_input["origin_type"]
            destination_type = user_input["destination_type"]
            origin = user_input["origin"]
            destination = user_input["destination"]
            via = user_input.get("via", "")
            avoid = user_input.get("avoid", "")
            max_walking_distance = user_input.get("max_walking_distance", 1000)
            refresh_interval = user_input.get("refresh_interval", DEFAULT_SCAN_INTERVAL)
            time_window = user_input.get("time_window", DEFAULT_TIME_WINDOW)

            # Basic validation for coordinates
            def valid_coords(val):
                try:
                    lat, lon = val.split(",")
                    float(lat)
                    float(lon)
                    return True
                except Exception:
                    return False

            if origin_type == "coordinates" and not valid_coords(origin):
                errors["origin"] = "invalid_coordinates"
            if destination_type == "coordinates" and not valid_coords(destination):
                errors["destination"] = "invalid_coordinates"

            if not errors:
                # Store config and create entry
                base_data = {
                    CONF_API_KEY: self._api_key,
                    CONF_NAME: self._name,
                    CONF_SENSOR_TYPE: self._sensor_type,
                    "origin_type": origin_type,
                    "origin": origin,
                    "destination_type": destination_type,
                    "destination": destination,
                }
                options_data = {
                    "via": via,
                    "avoid": avoid,
                    "max_walking_distance": max_walking_distance,
                    "refresh_interval": refresh_interval,
                    "time_window": time_window,
                }
                # Unique ID should be stable and not include name which can change
                unique_id = f"resrobot_{origin}_{destination}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = f"{self._name} Resrobot Travel Search"
                return self.async_create_entry(title=title, data=base_data, options=options_data)

        # Show form for Resrobot Travel Search config
        return self.async_show_form(
            step_id="resrobot",
            data_schema=resrobot_schema,
            errors=errors,
        )

    async def async_step_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the sensor configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Combine all configuration data
            # Immutable/base data
            base_data = {
                CONF_API_KEY: self._api_key,
                CONF_STOP_ID: self._stop_id,
                CONF_NAME: self._name,
                CONF_SENSOR_TYPE: user_input[CONF_SENSOR_TYPE],
            }
            # Mutable settings go to options to avoid redundancy
            options_data = {
                CONF_LINE_FILTER: user_input.get(CONF_LINE_FILTER, ""),
                CONF_DIRECTION: user_input.get(CONF_DIRECTION, ""),
                CONF_TIME_WINDOW: user_input.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                CONF_REFRESH_INTERVAL: user_input.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL),
                CONF_UPDATE_CONDITION: user_input.get(CONF_UPDATE_CONDITION, ""),
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
            sensor_type_name = "Departures" if user_input[CONF_SENSOR_TYPE] == SENSOR_TYPE_DEPARTURE else "Arrivals"
            title = f"{self._name} {sensor_type_name}"
            if user_input.get(CONF_LINE_FILTER):
                title += f" (Lines: {user_input[CONF_LINE_FILTER]})"

            return self.async_create_entry(title=title, data=base_data, options=options_data)

        return self.async_show_form(
            step_id="sensor", 
            data_schema=STEP_SENSOR_DATA_SCHEMA, 
            errors=errors,
            description_placeholders={
                "stop_id": self._stop_id,
                "stop_name": self._name,
            }
        )

    @staticmethod
    def async_get_options_flow(config_entry):  # type: ignore[override]
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for existing entries."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:  # noqa: D401
        data = self._entry.data
        options = self._entry.options

        def _opt(key: str, default: Any = ""):
            return options.get(key, data.get(key, default))

        is_resrobot = data.get(CONF_SENSOR_TYPE) == SENSOR_TYPE_RESROBOT

        if user_input is not None:
            prev_options = self._entry.options
            merged_options: dict[str, Any] = dict(prev_options)

            # Common numeric baselines
            if CONF_TIME_WINDOW not in merged_options:
                merged_options[CONF_TIME_WINDOW] = _opt(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)
            if CONF_REFRESH_INTERVAL not in merged_options:
                merged_options[CONF_REFRESH_INTERVAL] = _opt(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)

            if is_resrobot:
                # Merge Resrobot-specific options; only update keys provided
                for key in ("via", "avoid", "max_walking_distance", CONF_TIME_WINDOW, CONF_REFRESH_INTERVAL):
                    if key in user_input:
                        merged_options[key] = user_input[key]
            else:
                # Standard departure/arrival options; only update keys provided
                for key in (CONF_LINE_FILTER, CONF_DIRECTION, CONF_UPDATE_CONDITION, CONF_TIME_WINDOW, CONF_REFRESH_INTERVAL):
                    if key in user_input:
                        merged_options[key] = user_input[key]

            return self.async_create_entry(title="", data=merged_options)

        if is_resrobot:
            schema = vol.Schema({
                vol.Optional("via", default=_opt("via", "")): str,
                vol.Optional("avoid", default=_opt("avoid", "")): str,
                vol.Optional("max_walking_distance", default=_opt("max_walking_distance", 1000)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=10000)
                ),
                vol.Optional(CONF_REFRESH_INTERVAL, default=_opt(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(
                    vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
                ),
                vol.Optional(CONF_TIME_WINDOW, default=_opt(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=1440)
                ),
            })
        else:
            schema = vol.Schema({
                vol.Optional(CONF_LINE_FILTER, default=_opt(CONF_LINE_FILTER, "")): str,
                vol.Optional(CONF_DIRECTION, default=_opt(CONF_DIRECTION, "")): str,
                vol.Optional(CONF_TIME_WINDOW, default=_opt(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=1440)
                ),
                vol.Optional(CONF_REFRESH_INTERVAL, default=_opt(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL)): vol.All(
                    vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
                ),
                vol.Optional(CONF_UPDATE_CONDITION, default=_opt(CONF_UPDATE_CONDITION, "")): str,
            })

        return self.async_show_form(step_id="init", data_schema=schema)


# ---------------------------------------------------------------------------
# Validation helpers & custom exceptions (expected by tests)
# ---------------------------------------------------------------------------
class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class InvalidStopId(HomeAssistantError):
    """Error to indicate the stop id is invalid."""


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Returns minimal info dict. Raises custom exceptions on failure.
    Tests patch this function, so keep signature & return shape stable.
    """
    api_key = data[CONF_API_KEY]
    stop_id = data[CONF_STOP_ID]

    from homeassistant.helpers.aiohttp_client import async_get_clientsession
    client = TrafikLabApiClient(api_key, session=async_get_clientsession(hass))
    try:
        # Attempt a lightweight departures fetch to validate both key & stop.
        await client.get_departures(stop_id)
    except TrafikLabApiError as err:
        lower = str(err).lower()
        if "invalid api key" in lower or "authentication failed" in lower:
            raise InvalidApiKey from err
        if "not found" in lower or "stop id" in lower:
            raise InvalidStopId from err
        raise CannotConnect from err
    except Exception as err:  # pragma: no cover - network/aio edge case
        raise CannotConnect from err
    finally:
        await client.close()

    # Title used by tests when patched; we mirror behavior.
    return {"title": data.get(CONF_NAME, DEFAULT_NAME)}
