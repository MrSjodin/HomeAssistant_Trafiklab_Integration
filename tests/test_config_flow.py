"""Test the Trafiklab config flow."""
import pytest
from unittest.mock import patch, AsyncMock
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.trafiklab.const import (
    DOMAIN, 
    CONF_API_KEY, 
    CONF_STOP_ID,
    CONF_SENSOR_TYPE,
    CONF_LINE_FILTER,
    CONF_DIRECTION,
    CONF_TIME_WINDOW,
    CONF_REFRESH_INTERVAL,
    SENSOR_TYPE_DEPARTURE,
    DEFAULT_SCAN_INTERVAL,
)
from custom_components.trafiklab.config_flow import (
    CannotConnect,
    InvalidApiKey,
    InvalidStopId,
)


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "custom_components.trafiklab.config_flow.validate_input",
        return_value={"title": "Test"},
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_api_key",
                CONF_STOP_ID: "9001",
                "name": "Test",
            },
        )

    # Should go to sensor configuration step
    assert result2["type"] == FlowResultType.FORM
    assert result2["step_id"] == "sensor"

    # Complete sensor configuration
    with patch(
        "custom_components.trafiklab.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {
                CONF_SENSOR_TYPE: SENSOR_TYPE_DEPARTURE,
                CONF_LINE_FILTER: "",
                CONF_DIRECTION: "",
                CONF_TIME_WINDOW: 60,
                CONF_REFRESH_INTERVAL: DEFAULT_SCAN_INTERVAL,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] == FlowResultType.CREATE_ENTRY
    assert result3["title"] == "Test Departures"
    assert result3["data"][CONF_API_KEY] == "test_api_key"
    assert result3["data"][CONF_STOP_ID] == "9001"
    assert result3["data"][CONF_SENSOR_TYPE] == SENSOR_TYPE_DEPARTURE
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_api_key(hass: HomeAssistant) -> None:
    """Test we handle invalid API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.trafiklab.config_flow.validate_input",
        side_effect=InvalidApiKey,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "invalid_key",
                CONF_STOP_ID: "9001",
                "name": "Test",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"api_key": "Invalid API key"}


async def test_form_invalid_stop_id(hass: HomeAssistant) -> None:
    """Test we handle invalid stop ID."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.trafiklab.config_flow.validate_input",
        side_effect=InvalidStopId,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_api_key",
                CONF_STOP_ID: "invalid_stop",
                "name": "Test",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"stop_id": "Stop not found"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "custom_components.trafiklab.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test_api_key",
                CONF_STOP_ID: "9001",
                "name": "Test",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "Connection error"}
