"""Config flow for Trafiklab integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME as HA_CONF_NAME  # avoid collision; not used
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .api import (
    TrafikLabApiClient,
    TrafikLabApiError,
    TrafikLabAuthError,
    TrafikLabQuotaError,
    TrafikLabNotFoundError,
)

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
    CONF_MAX_TRIP_DURATION,
    CONF_MAX_RESULTS,
    DEFAULT_MAX_RESULTS,
    CONF_TRANSPORT_MODES,
    CONF_INCLUDE_PLATFORM,
)

_LOGGER = logging.getLogger(__name__)

_TRANSPORT_MODES_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["bus", "metro", "train", "tram", "boat"],
        multiple=True,
        mode=SelectSelectorMode.LIST,
        translation_key="transport_modes",
    )
)

_SENSOR_TYPE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL, SENSOR_TYPE_RESROBOT],
        multiple=False,
        mode=SelectSelectorMode.LIST,
        translation_key="sensor_type",
    )
)

_SENSOR_TYPE_DEP_ARR_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=[SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL],
        multiple=False,
        mode=SelectSelectorMode.LIST,
        translation_key="sensor_type",
    )
)

_LOCATION_TYPE_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=["stop_id", "coordinates"],
        multiple=False,
        mode=SelectSelectorMode.LIST,
        translation_key="origin_type",
    )
)


STEP_SENSOR_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SENSOR_TYPE, default=SENSOR_TYPE_DEPARTURE): _SENSOR_TYPE_DEP_ARR_SELECTOR,
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
        vol.Optional(CONF_TRANSPORT_MODES, default=[]): _TRANSPORT_MODES_SELECTOR,
        vol.Optional(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Trafiklab."""

    VERSION = 3


    def __init__(self):
        """Initialize config flow."""
        self._api_key = None
        self._stop_id = None
        self._name = None
        self._sensor_type = None
        self._api_key_rejected = False


    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: sensor type and API key."""
        errors: dict[str, str] = {}
        error_detail = ""

        if user_input is not None:
                # Legacy path: allow initial form to accept api_key + stop_id (+ name)
                if CONF_STOP_ID in user_input and CONF_API_KEY in user_input and CONF_SENSOR_TYPE not in user_input:
                    self._api_key = user_input[CONF_API_KEY].strip()
                    self._stop_id = user_input[CONF_STOP_ID]
                    self._name = ""
                    try:
                        await validate_input(self.hass, {
                            CONF_API_KEY: self._api_key,
                            CONF_STOP_ID: self._stop_id,
                        })
                    except InvalidApiKey as err:
                        errors["api_key"] = "invalid_api_key"
                        error_detail = _error_detail(err)
                    except InvalidStopId as err:
                        # The initial form has no stop field, report on the form itself
                        errors["base"] = "invalid_stop_id"
                        error_detail = _error_detail(err)
                    except QuotaExceeded as err:
                        errors["base"] = "quota_exceeded"
                        error_detail = _error_detail(err)
                    except CannotConnect as err:
                        errors["base"] = "cannot_connect"
                        error_detail = _error_detail(err)
                    except Exception as err:  # pragma: no cover
                        _LOGGER.exception("Unexpected exception during validation: %s", err)
                        errors["base"] = "unknown"
                        error_detail = _error_detail(err)
                    else:
                        # Proceed to sensor configuration step
                        return await self.async_step_sensor()
                else:
                    # New path: choose sensor type first
                    self._sensor_type = user_input[CONF_SENSOR_TYPE]
                    self._api_key = user_input[CONF_API_KEY].strip()
                    self._api_key_rejected = False
                    self._name = user_input.get(CONF_NAME, "")
                    # Next step depends on sensor type
                    if self._sensor_type in [SENSOR_TYPE_DEPARTURE, SENSOR_TYPE_ARRIVAL]:
                        return await self.async_step_departure_arrival()
                    elif self._sensor_type == SENSOR_TYPE_RESROBOT:
                        return await self.async_step_resrobot()

        # Show initial form
        dynamic_schema = vol.Schema(
            {
                vol.Required(CONF_SENSOR_TYPE, default=SENSOR_TYPE_RESROBOT): _SENSOR_TYPE_SELECTOR,
                vol.Required(CONF_API_KEY): str,
                vol.Optional(CONF_NAME, default=""): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(dynamic_schema, user_input or {}),
            errors=errors,
            description_placeholders={"error_detail": error_detail},
        )

    async def async_step_departure_arrival(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for Departure/Arrival sensor config."""
        errors: dict[str, str] = {}
        error_detail = ""

        if user_input is not None:
            self._stop_id = user_input[CONF_STOP_ID]
            # The API key field is only shown after the key was rejected
            if user_input.get(CONF_API_KEY):
                self._api_key = user_input[CONF_API_KEY].strip()
            # Validate input as before
            try:
                await validate_input(self.hass, {
                    CONF_API_KEY: self._api_key,
                    CONF_STOP_ID: self._stop_id,
                })
            except InvalidApiKey as err:
                errors["api_key"] = "invalid_api_key"
                self._api_key_rejected = True
                error_detail = _error_detail(err)
            except InvalidStopId as err:
                errors["stop_id"] = "invalid_stop_id"
                error_detail = _error_detail(err)
            except QuotaExceeded as err:
                errors["base"] = "quota_exceeded"
                error_detail = _error_detail(err)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                error_detail = _error_detail(err)
            except Exception as err:
                _LOGGER.exception("Unexpected exception during validation: %s", err)
                errors["base"] = "unknown"
                error_detail = _error_detail(err)
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
                    CONF_TRANSPORT_MODES: user_input.get(CONF_TRANSPORT_MODES, []),
                    CONF_TIME_WINDOW: user_input.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                    CONF_REFRESH_INTERVAL: user_input.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    CONF_UPDATE_CONDITION: user_input.get(CONF_UPDATE_CONDITION, ""),
                    CONF_MAX_RESULTS: user_input.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS),
                }
                unique_id = f"{self._stop_id}_{self._sensor_type}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                sensor_type_name = "Departures" if self._sensor_type == SENSOR_TYPE_DEPARTURE else "Arrivals"
                title = f"{self._name} {sensor_type_name}".strip()
                return self.async_create_entry(title=title, data=base_data, options=options_data)

        # Show form for Departure/Arrival sensor config. When the API key has
        # been rejected, include it so the error is visible and can be fixed.
        fields: dict[Any, Any] = {}
        if self._api_key_rejected:
            fields[vol.Optional(CONF_API_KEY)] = str
        schema = vol.Schema({
                **fields,
                vol.Required(CONF_STOP_ID): str,
                vol.Optional(CONF_LINE_FILTER, default=""): str,
                vol.Optional(CONF_DIRECTION, default=""): str,
                vol.Optional(CONF_TRANSPORT_MODES, default=[]): _TRANSPORT_MODES_SELECTOR,
                vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=1440)
                ),
                vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
                ),
                vol.Optional(CONF_UPDATE_CONDITION, default=""): str,
                vol.Optional(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=100)
                ),
            })
        # Keep what the user entered when the form is shown again after an error
        suggested = {**(user_input or {})}
        if self._api_key_rejected:
            suggested[CONF_API_KEY] = self._api_key or ""
        return self.async_show_form(
            step_id="departure_arrival",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
            description_placeholders={"error_detail": error_detail},
        )

    async def async_step_resrobot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the step for Resrobot Travel Search sensor config."""
        errors: dict[str, str] = {}
        error_detail = ""

        if user_input is not None and user_input.get(CONF_API_KEY):
            # The API key field is only shown after the key was rejected
            self._api_key = user_input[CONF_API_KEY].strip()

        # Define all required fields for Resrobot, including update frequency and time window
        # Keep options simple; labels are translated via step strings
        resrobot_schema_fields = {
            vol.Required(CONF_ORIGIN_TYPE, default="stop_id"): _LOCATION_TYPE_SELECTOR,
            vol.Required(CONF_ORIGIN, default=""): str,
            vol.Required(CONF_DESTINATION_TYPE, default="stop_id"): _LOCATION_TYPE_SELECTOR,
            vol.Required(CONF_DESTINATION, default=""): str,
            vol.Optional(CONF_VIA, default=""): str,
            vol.Optional(CONF_AVOID, default=""): str,
            vol.Optional(CONF_MAX_WALKING_DISTANCE, default=1000): vol.All(vol.Coerce(int), vol.Range(min=0, max=10000)),
            vol.Optional(CONF_MAX_TRIP_DURATION, default=None): vol.Any(None, vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))),
            vol.Optional(CONF_TRANSPORT_MODES, default=[]): _TRANSPORT_MODES_SELECTOR,
            vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)),
            vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
            vol.Optional(CONF_INCLUDE_PLATFORM, default=False): bool,
            vol.Optional(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
        }

        if user_input is not None:
            # Validate origin/destination types and values
            origin_type = user_input["origin_type"]
            destination_type = user_input["destination_type"]
            origin = user_input["origin"]
            destination = user_input["destination"]
            via = user_input.get("via", "")
            avoid = user_input.get("avoid", "")
            max_walking_distance = user_input.get("max_walking_distance", 1000)
            max_trip_duration = user_input.get(CONF_MAX_TRIP_DURATION)
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
                # Probe Resrobot API to validate the key before saving
                from homeassistant.helpers.aiohttp_client import async_get_clientsession
                _probe_client = TrafikLabApiClient(
                    self._api_key, session=async_get_clientsession(self.hass)
                )
                try:
                    await _probe_client.search_resrobot_stops("Stockholm", self._api_key)
                except TrafikLabAuthError as err:
                    errors["api_key"] = "invalid_api_key"
                    self._api_key_rejected = True
                    error_detail = _error_detail(err)
                except TrafikLabQuotaError as err:
                    errors["base"] = "quota_exceeded"
                    error_detail = _error_detail(err)
                except TrafikLabApiError as err:
                    errors["base"] = "cannot_connect"
                    error_detail = _error_detail(err)
                except Exception as err:  # pragma: no cover
                    errors["base"] = "cannot_connect"
                    error_detail = _error_detail(err)
                finally:
                    await _probe_client.close()

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
                    CONF_MAX_TRIP_DURATION: user_input.get(CONF_MAX_TRIP_DURATION),
                    CONF_TRANSPORT_MODES: user_input.get(CONF_TRANSPORT_MODES, []),
                    "refresh_interval": refresh_interval,
                    "time_window": time_window,
                    CONF_INCLUDE_PLATFORM: user_input.get(CONF_INCLUDE_PLATFORM, False),
                    CONF_MAX_RESULTS: user_input.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS),
                }
                # Unique ID should be stable and not include name which can change
                unique_id = f"resrobot_{origin}_{destination}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                title = f"{self._name} Resrobot Travel Search".strip()
                return self.async_create_entry(title=title, data=base_data, options=options_data)

        # Show form for Resrobot Travel Search config. When the API key has
        # been rejected, include it so the error is visible and can be fixed.
        if self._api_key_rejected:
            resrobot_schema_fields = {
                vol.Optional(CONF_API_KEY): str,
                **resrobot_schema_fields,
            }
        # Keep what the user entered when the form is shown again after an error
        suggested = {**(user_input or {})}
        if self._api_key_rejected:
            suggested[CONF_API_KEY] = self._api_key or ""
        return self.async_show_form(
            step_id="resrobot",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(resrobot_schema_fields), suggested
            ),
            errors=errors,
            description_placeholders={"error_detail": error_detail},
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
                CONF_TRANSPORT_MODES: user_input.get(CONF_TRANSPORT_MODES, []),
                CONF_TIME_WINDOW: user_input.get(CONF_TIME_WINDOW, DEFAULT_TIME_WINDOW),
                CONF_REFRESH_INTERVAL: user_input.get(CONF_REFRESH_INTERVAL, DEFAULT_SCAN_INTERVAL),
                CONF_UPDATE_CONDITION: user_input.get(CONF_UPDATE_CONDITION, ""),
                CONF_MAX_RESULTS: user_input.get(CONF_MAX_RESULTS, DEFAULT_MAX_RESULTS),
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
            title = f"{self._name} {sensor_type_name}".strip()
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of an existing entry (change data fields)."""
        entry = self._get_reconfigure_entry()
        sensor_type = entry.data.get(CONF_SENSOR_TYPE)
        if sensor_type == SENSOR_TYPE_RESROBOT:
            return await self.async_step_reconfigure_resrobot(user_input)
        return await self.async_step_reconfigure_departure_arrival(user_input)

    async def async_step_reconfigure_departure_arrival(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure API key and stop ID for a departure/arrival sensor."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        error_detail = ""

        if user_input is not None:
            user_input = {**user_input, CONF_API_KEY: user_input[CONF_API_KEY].strip()}
            try:
                await validate_input(self.hass, {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_STOP_ID: user_input[CONF_STOP_ID],
                })
            except InvalidApiKey as err:
                errors["api_key"] = "invalid_api_key"
                error_detail = _error_detail(err)
            except InvalidStopId as err:
                errors["stop_id"] = "invalid_stop_id"
                error_detail = _error_detail(err)
            except QuotaExceeded as err:
                errors["base"] = "quota_exceeded"
                error_detail = _error_detail(err)
            except CannotConnect as err:
                errors["base"] = "cannot_connect"
                error_detail = _error_detail(err)
            except Exception as err:
                _LOGGER.exception("Unexpected exception during reconfigure validation: %s", err)
                errors["base"] = "unknown"
                error_detail = _error_detail(err)
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                )

        schema = vol.Schema({
            vol.Required(CONF_API_KEY, default=entry.data.get(CONF_API_KEY, "")): str,
            vol.Required(CONF_STOP_ID, default=entry.data.get(CONF_STOP_ID, "")): str,
        })
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={"error_detail": error_detail},
        )

    async def async_step_reconfigure_resrobot(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure API key and trip endpoints for a Resrobot sensor."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        error_detail = ""

        def valid_coords(val: str) -> bool:
            try:
                lat, lon = val.split(",")
                float(lat)
                float(lon)
                return True
            except Exception:
                return False

        if user_input is not None:
            user_input = {**user_input, CONF_API_KEY: user_input[CONF_API_KEY].strip()}
            if user_input.get(CONF_ORIGIN_TYPE) == "coordinates" and not valid_coords(user_input.get(CONF_ORIGIN, "")):
                errors[CONF_ORIGIN] = "invalid_coordinates"
            if user_input.get(CONF_DESTINATION_TYPE) == "coordinates" and not valid_coords(user_input.get(CONF_DESTINATION, "")):
                errors[CONF_DESTINATION] = "invalid_coordinates"

            if not errors:
                # Probe Resrobot API to validate the key before saving
                from homeassistant.helpers.aiohttp_client import async_get_clientsession
                _probe_client = TrafikLabApiClient(
                    user_input[CONF_API_KEY], session=async_get_clientsession(self.hass)
                )
                try:
                    await _probe_client.search_resrobot_stops("Stockholm", user_input[CONF_API_KEY])
                except TrafikLabAuthError as err:
                    errors["api_key"] = "invalid_api_key"
                    error_detail = _error_detail(err)
                except TrafikLabQuotaError as err:
                    errors["base"] = "quota_exceeded"
                    error_detail = _error_detail(err)
                except TrafikLabApiError as err:
                    errors["base"] = "cannot_connect"
                    error_detail = _error_detail(err)
                except Exception as err:  # pragma: no cover
                    errors["base"] = "cannot_connect"
                    error_detail = _error_detail(err)
                finally:
                    await _probe_client.close()

            if not errors:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, **user_input},
                )

        schema = vol.Schema({
            vol.Required(CONF_API_KEY, default=entry.data.get(CONF_API_KEY, "")): str,
            vol.Required(CONF_ORIGIN_TYPE, default=entry.data.get(CONF_ORIGIN_TYPE, "stop_id")): _LOCATION_TYPE_SELECTOR,
            vol.Required(CONF_ORIGIN, default=entry.data.get(CONF_ORIGIN, "")): str,
            vol.Required(CONF_DESTINATION_TYPE, default=entry.data.get(CONF_DESTINATION_TYPE, "stop_id")): _LOCATION_TYPE_SELECTOR,
            vol.Required(CONF_DESTINATION, default=entry.data.get(CONF_DESTINATION, "")): str,
        })
        return self.async_show_form(
            step_id="reconfigure_resrobot",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
            description_placeholders={"error_detail": error_detail},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):  # type: ignore[override]
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for existing entries."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__()
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:  # noqa: D401
        is_resrobot = self._entry.data.get(CONF_SENSOR_TYPE) == SENSOR_TYPE_RESROBOT

        if is_resrobot:
            return await self.async_step_init_resrobot(user_input)

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(CONF_LINE_FILTER, default=""): str,
            vol.Optional(CONF_DIRECTION, default=""): str,
            vol.Optional(CONF_TRANSPORT_MODES, default=[]): _TRANSPORT_MODES_SELECTOR,
            vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1440)
            ),
            vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
            ),
            vol.Optional(CONF_UPDATE_CONDITION, default=""): str,
            vol.Optional(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
        })
        current_values = {**self._entry.data, **self._entry.options}
        # Normalize transport_modes: old entries may lack the key, have None stored,
        # or contain values no longer in the valid set (e.g. the old "ship" key).
        # add_suggested_values_to_schema passes whatever is here to the frontend as
        # suggested_value; invalid/null elements cause "value must be one of [...]".
        current_values[CONF_TRANSPORT_MODES] = [
            m for m in (current_values.get(CONF_TRANSPORT_MODES) or [])
            if isinstance(m, str) and m in {"bus", "metro", "train", "tram", "boat"}
        ]
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, current_values),
        )

    async def async_step_init_resrobot(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Options step for Resrobot Travel Search sensors."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema({
            vol.Optional(CONF_VIA, default=""): str,
            vol.Optional(CONF_AVOID, default=""): str,
            vol.Optional(CONF_MAX_WALKING_DISTANCE, default=1000): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=10000)
            ),
            vol.Optional(CONF_MAX_TRIP_DURATION, default=None): vol.Any(
                None, vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))
            ),
            vol.Optional(CONF_TRANSPORT_MODES, default=[]): _TRANSPORT_MODES_SELECTOR,
            vol.Optional(CONF_REFRESH_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                vol.Coerce(int), vol.Range(min=MINIMUM_SCAN_INTERVAL, max=3600)
            ),
            vol.Optional(CONF_TIME_WINDOW, default=DEFAULT_TIME_WINDOW): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=1440)
            ),
            vol.Optional(CONF_INCLUDE_PLATFORM, default=False): bool,
            vol.Optional(CONF_MAX_RESULTS, default=DEFAULT_MAX_RESULTS): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
        })
        current_values = {**self._entry.data, **self._entry.options}
        # Normalize transport_modes: old entries may lack the key, have None stored,
        # or contain values no longer in the valid set (e.g. the old "ship" key).
        # add_suggested_values_to_schema passes whatever is here to the frontend as
        # suggested_value; invalid/null elements cause "value must be one of [...]".
        current_values[CONF_TRANSPORT_MODES] = [
            m for m in (current_values.get(CONF_TRANSPORT_MODES) or [])
            if isinstance(m, str) and m in {"bus", "metro", "train", "tram", "boat"}
        ]
        return self.async_show_form(
            step_id="init_resrobot",
            data_schema=self.add_suggested_values_to_schema(schema, current_values),
        )


# ---------------------------------------------------------------------------
# Validation helpers & custom exceptions (expected by tests)
# ---------------------------------------------------------------------------
def _error_detail(err: BaseException) -> str:
    """Return the error message from the API, for the form's error text."""
    detail = str(err).strip()
    if not detail and err.__cause__ is not None:
        detail = str(err.__cause__).strip()
    return detail or type(err).__name__


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidApiKey(HomeAssistantError):
    """Error to indicate the API key is invalid."""


class InvalidStopId(HomeAssistantError):
    """Error to indicate the stop id is invalid."""


class QuotaExceeded(HomeAssistantError):
    """Error to indicate the API quota has been exceeded."""


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
    except TrafikLabAuthError as err:
        raise InvalidApiKey(str(err)) from err
    except TrafikLabNotFoundError as err:
        raise InvalidStopId(str(err)) from err
    except TrafikLabQuotaError as err:
        raise QuotaExceeded(str(err)) from err
    except TrafikLabApiError as err:
        raise CannotConnect(str(err)) from err
    except Exception as err:  # pragma: no cover - network/aio edge case
        raise CannotConnect(str(err)) from err
    finally:
        await client.close()

    # Title used by tests when patched; we mirror behavior.
    return {"title": data.get(CONF_NAME, "")}
