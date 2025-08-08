"""Test the Trafiklab init."""
import pytest
from unittest.mock import patch, AsyncMock
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.trafiklab import async_setup_entry, async_unload_entry
from custom_components.trafiklab.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant, mock_config_entry: ConfigEntry) -> None:
    """Test setting up the integration."""
    with patch(
        "custom_components.trafiklab.coordinator.TrafikLabCoordinator.async_config_entry_first_refresh",
        return_value=None,
    ), patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as mock_forward:
        result = await async_setup_entry(hass, mock_config_entry)
        
    assert result is True
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    mock_forward.assert_called_once()


async def test_unload_entry(hass: HomeAssistant, mock_config_entry: ConfigEntry) -> None:
    """Test unloading the integration."""
    # First set up the integration
    hass.data[DOMAIN] = {mock_config_entry.entry_id: "test_coordinator"}
    
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        result = await async_unload_entry(hass, mock_config_entry)
        
    assert result is True
    assert mock_config_entry.entry_id not in hass.data[DOMAIN]
    mock_unload.assert_called_once()
