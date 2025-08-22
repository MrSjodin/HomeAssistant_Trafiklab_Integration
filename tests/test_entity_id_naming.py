"""Test entity_id naming scheme for newly created sensors."""
import pytest
from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntry

from custom_components.trafiklab.const import (
    DOMAIN,
    CONF_NAME,
    CONF_SENSOR_TYPE,
    SENSOR_TYPE_DEPARTURE,
    SENSOR_TYPE_ARRIVAL,
    SENSOR_TYPE_RESROBOT,
)
from custom_components.trafiklab.sensor import TrafikLabSensor, SensorEntityDescription


@pytest.mark.asyncio
async def test_departure_sensor_suggested_entity_id_english():
    entry = ConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Trafiklab Test",
        data={
            CONF_NAME: "Central Station",
            CONF_SENSOR_TYPE: SENSOR_TYPE_DEPARTURE,
        },
        options={},
        entry_id="entry_dep",
    )
    coord = MagicMock()
    desc = SensorEntityDescription(
        key="next_departure",
        translation_key="next_departure",
        icon="mdi:bus-clock",
        native_unit_of_measurement="min",
    )
    sensor = TrafikLabSensor(coord, entry, desc)
    assert sensor._attr_suggested_object_id == "trafiklab_departures_central_station"


@pytest.mark.asyncio
async def test_arrival_sensor_suggested_entity_id_english():
    entry = ConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Trafiklab Test",
        data={
            CONF_NAME: "T-Centralen",
            CONF_SENSOR_TYPE: SENSOR_TYPE_ARRIVAL,
        },
        options={},
        entry_id="entry_arr",
    )
    coord = MagicMock()
    desc = SensorEntityDescription(
        key="next_arrival",
        translation_key="next_arrival",
        icon="mdi:bus-stop",
        native_unit_of_measurement="min",
    )
    sensor = TrafikLabSensor(coord, entry, desc)
    assert sensor._attr_suggested_object_id == "trafiklab_arrivals_t_centralen"


@pytest.mark.asyncio
async def test_resrobot_sensor_suggested_entity_id_english():
    entry = ConfigEntry(
        version=2,
        domain=DOMAIN,
        title="Trafiklab Test",
        data={
            CONF_NAME: "Home to Work",
            CONF_SENSOR_TYPE: SENSOR_TYPE_RESROBOT,
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={},
        entry_id="entry_res",
    )
    coord = MagicMock()
    desc = SensorEntityDescription(
        key="resrobot_travel",
        translation_key="resrobot_travel",
        icon="mdi:train-car",
        native_unit_of_measurement="min",
    )
    sensor = TrafikLabSensor(coord, entry, desc)
    assert sensor._attr_suggested_object_id == "trafiklab_travel_home_to_work"
