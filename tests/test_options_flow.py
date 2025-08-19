"""Tests for the Trafiklab options flow behavior."""
from __future__ import annotations

import pytest
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import (
    DOMAIN,
    CONF_LINE_FILTER,
    CONF_DIRECTION,
    CONF_TIME_WINDOW,
    CONF_REFRESH_INTERVAL,
)


@pytest.mark.asyncio
async def test_options_flow_clearing_line_filter_persists(hass: HomeAssistant) -> None:
    """Clearing the line filter in options should save an empty string, not revert."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "x", "stop_id": "y", "sensor_type": "departure", "name": "Test"},
        options={CONF_LINE_FILTER: "1,2", CONF_TIME_WINDOW: 60, CONF_REFRESH_INTERVAL: 300},
        unique_id="y_departure",
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    # Submit with an explicit empty string to clear the filter; omit numeric fields
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_LINE_FILTER: ""}
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options.get(CONF_LINE_FILTER) == ""
    # Unchanged fields remain
    assert entry.options.get(CONF_TIME_WINDOW) == 60
    assert entry.options.get(CONF_REFRESH_INTERVAL) == 300


@pytest.mark.asyncio
async def test_options_flow_preserves_when_omitted(hass: HomeAssistant) -> None:
    """Omitting text fields should preserve previous values; providing empty clears."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "x", "stop_id": "y", "sensor_type": "departure", "name": "Test"},
        options={CONF_LINE_FILTER: "10", CONF_DIRECTION: "Central"},
        unique_id="y_departure",
        version=2,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    # Do not include CONF_LINE_FILTER in submission -> should keep "10"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_DIRECTION: ""}  # explicitly clear direction only
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    # Line filter preserved since it was omitted
    assert entry.options.get(CONF_LINE_FILTER) == "10"
    # Direction cleared
    assert entry.options.get(CONF_DIRECTION) == ""
