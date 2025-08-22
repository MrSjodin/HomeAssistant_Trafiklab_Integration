"""Test TrafiklabSensor entity for Resrobot sensor type."""
import pytest
from unittest.mock import MagicMock
from homeassistant.config_entries import ConfigEntry
from custom_components.trafiklab.const import DOMAIN, SENSOR_TYPE_RESROBOT
from custom_components.trafiklab.sensor import TrafikLabSensor, SensorEntityDescription

@pytest.mark.asyncio
async def test_sensor_resrobot_attributes():
    """Test sensor exposes correct value and attributes for Resrobot data."""
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
    # Mock coordinator with Resrobot data
    mock_coordinator = MagicMock()
    mock_coordinator.data = {
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
    mock_coordinator.last_successful_update = "2025-08-21T12:00:00+00:00"
    description = SensorEntityDescription(
        key="resrobot_travel",
        translation_key="resrobot_travel",
        icon="mdi:train-car",
        native_unit_of_measurement="min",
    )
    sensor = TrafikLabSensor(mock_coordinator, entry, description)
    # Test native_value (minutes to departure)
    value = sensor.native_value
    assert isinstance(value, int)
    # Test extra_state_attributes (trips + per-trip legs only)
    attrs = sensor.extra_state_attributes
    assert "num_trips" in attrs
    assert "trips" in attrs
    assert isinstance(attrs["trips"], list)
    assert len(attrs["trips"]) >= 1
    first_trip = attrs["trips"][0]
    assert "legs" in first_trip
    assert isinstance(first_trip["legs"], list)
    assert len(first_trip["legs"]) >= 1
    first_leg = first_trip["legs"][0]
    assert first_leg["origin_name"] == "A"
    assert first_leg["dest_name"] == "B"
    assert first_leg["type"] == "BUS"
    assert first_leg["product"] == "Bus 1"
    assert first_leg["direction"] == "Central Station"
    assert attrs["attribution"] == "Data from Resrobot/Trafiklab.se"
    assert attrs["last_update"] == "2025-08-21T12:00:00+00:00"
