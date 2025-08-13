"""Pytest fixtures for Trafiklab integration tests."""
from __future__ import annotations

import pytest
from homeassistant.const import CONF_API_KEY, CONF_STOP_ID, CONF_SENSOR_TYPE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import entity_registry as er

from custom_components.trafiklab.const import DOMAIN, SENSOR_TYPE_DEPARTURE, DEFAULT_NAME


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> ConfigEntry:
    """Return a mock config entry for the integration."""
    data = {
        CONF_API_KEY: "test_api_key",
        CONF_STOP_ID: "9001",
        CONF_SENSOR_TYPE: SENSOR_TYPE_DEPARTURE,
        CONF_NAME: DEFAULT_NAME,
    }
    entry = ConfigEntry(
        version=2,
        minor_version=0,
        domain=DOMAIN,
        title="Trafiklab Test",
        data=data,
        source="user",
        entry_id="test-entry-id",
    )
    hass.config_entries._entries.append(entry)  # type: ignore[attr-defined]
    return entry
