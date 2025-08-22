"""Test TrafiklabCoordinator logic for Resrobot sensor type."""
import pytest
from unittest.mock import AsyncMock
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from custom_components.trafiklab.const import DOMAIN, SENSOR_TYPE_RESROBOT
from custom_components.trafiklab.coordinator import TrafikLabCoordinator

@pytest.mark.asyncio
async def test_coordinator_resrobot_fetch(hass: HomeAssistant, monkeypatch):
    """Test coordinator fetches Resrobot data and parses response."""
    # Mock config entry for Resrobot
    entry = ConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Resrobot Test",
        data={
            "api_key": "resrobot_key",
            "sensor_type": SENSOR_TYPE_RESROBOT,
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "coordinates",
            "destination": "59.3293,18.0686",
            "name": "Resrobot Test",
        },
        options={
            "via": "",
            "avoid": "",
            "max_walking_distance": 1000,
        },
        entry_id="test_id",
    )
    # Patch API client method
    mock_response = {
        "Trip": [
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "A", "date": "2025-08-21", "time": "12:00"},
                            "Destination": {"name": "B", "date": "2025-08-21", "time": "12:30"},
                            "type": "BUS",
                            "Product": {"name": "Bus 1", "catOut": "Bus"},
                            "direction": "Central Station",
                        }
                    ]
                }
            }
        ]
    }
    monkeypatch.setattr(
        "custom_components.trafiklab.api.TrafikLabApiClient.get_resrobot_travel_search",
        AsyncMock(return_value=mock_response),
    )
    coordinator = TrafikLabCoordinator(hass, entry)
    data = await coordinator._async_update_data()
    assert "Trip" in data
    assert data["Trip"][0]["LegList"]["Leg"][0]["Origin"]["name"] == "A"
    assert coordinator.last_successful_update is not None
