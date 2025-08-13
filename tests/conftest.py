"""Pytest fixtures for Trafiklab integration tests."""
from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import (
    DOMAIN,
    CONF_API_KEY,
    CONF_STOP_ID,
    CONF_SENSOR_TYPE,
    DEFAULT_NAME,
)
from custom_components.trafiklab.const import SENSOR_TYPE_DEPARTURE  # separate to keep grouping clear


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> ConfigEntry:  # type: ignore[override]
    """Provide a mock config entry added to hass."""
    data = {
        CONF_API_KEY: "test_api_key",
        CONF_STOP_ID: "9001",
        CONF_SENSOR_TYPE: SENSOR_TYPE_DEPARTURE,
        "name": DEFAULT_NAME,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=data,
        title="Trafiklab Test",
        version=2,
        unique_id="9001_departure",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(autouse=True)
def _auto_enable_custom_integrations(enable_custom_integrations):  # noqa: D401
    """Automatically enable loading of custom_components directory."""
    yield
