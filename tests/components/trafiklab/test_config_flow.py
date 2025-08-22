from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN
from custom_components.trafiklab.config_flow import CannotConnect, InvalidApiKey, InvalidStopId


@pytest.mark.asyncio
async def test_flow_user_selects_departure_and_configures_stop(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == "form"

    # Choose departures type
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sensor_type": "departure", "api_key": "key", "name": "My Stop"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "departure_arrival"

    # Validate helper is called and succeeds
    with patch("custom_components.trafiklab.config_flow.validate_input", return_value={"title": "My Stop"}):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"stop_id": "740098000", "line_filter": "52", "direction": "Central", "time_window": 60, "refresh_interval": 300},
        )

    assert result["type"] == "create_entry"
    assert result["data"]["api_key"] == "key"
    assert result["data"]["stop_id"] == "740098000"
    assert result["options"]["line_filter"] == "52"


@pytest.mark.asyncio
async def test_flow_user_resrobot_path(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == "form"

    # Choose Resrobot
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sensor_type": "resrobot_travel_search", "api_key": "key", "name": "Travel"},
    )
    assert result["type"] == "form"
    assert result["step_id"] == "resrobot"

    # Provide details and finish
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
            "via": "",
            "avoid": "",
            "max_walking_distance": 1000,
            "refresh_interval": 300,
            "time_window": 60,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"]["sensor_type"] == "resrobot_travel_search"
    assert result["options"]["max_walking_distance"] == 1000


@pytest.mark.asyncio
async def test_flow_errors_mapped(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"sensor_type": "departure", "api_key": "key", "name": "My Stop"},
    )
    # Invalid API key
    with patch("custom_components.trafiklab.config_flow.validate_input", side_effect=InvalidApiKey()):
        result_err = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stop_id": "1"}
        )
    assert result_err["type"] == "form"
    assert result_err["errors"].get("api_key") == "invalid_api_key"

    # Invalid stop id
    with patch("custom_components.trafiklab.config_flow.validate_input", side_effect=InvalidStopId()):
        result_err = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stop_id": "1"}
        )
    assert result_err["errors"].get("stop_id") == "invalid_stop_id"

    # Cannot connect
    with patch("custom_components.trafiklab.config_flow.validate_input", side_effect=CannotConnect()):
        result_err = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"stop_id": "1"}
        )
    assert result_err["errors"].get("base") == "cannot_connect"


@pytest.mark.asyncio
async def test_options_flow_departure(hass: HomeAssistant, enable_custom_integrations: None) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={},
        unique_id="uid",
    )
    entry.add_to_hass(hass)
    # Use handler directly to avoid full HA UI machinery
    from custom_components.trafiklab.config_flow import OptionsFlowHandler
    handler = OptionsFlowHandler(entry)
    result = await handler.async_step_init({
        "line_filter": "52",
        "direction": "Cent",
        "time_window": 30,
        "refresh_interval": 120,
        "update_condition": "true",
    })
    assert result["type"] == "create_entry"
    assert result["data"]["line_filter"] == "52"
