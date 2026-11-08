"""Tests for the Trafiklab calendar platform."""
from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN

from tests.components.trafiklab.const import (
    ENTRY_DATA_DEPARTURE,
    ENTRY_DATA_RESROBOT,
    ENTRY_OPTIONS_DEFAULT,
    ENTRY_OPTIONS_RESROBOT,
)

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")

_UPDATE = "custom_components.trafiklab.coordinator.TrafikLabCoordinator._async_update_data"
_STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _local(minutes: int) -> datetime:
    """Swedish local time `minutes` from now, as the API reports it (no offset)."""
    return (datetime.now(_STOCKHOLM) + timedelta(minutes=minutes)).replace(
        tzinfo=None, microsecond=0
    )


def _departure(line: str, direction: str, minutes: int, **extra) -> dict:
    when = _local(minutes).isoformat()
    item = {
        "scheduled": when,
        "realtime": when,
        "is_realtime": True,
        "delay": 0,
        "canceled": False,
        "realtime_platform": {"designation": "B"},
        "scheduled_platform": {"designation": "B"},
        "route": {"designation": line, "direction": direction, "transport_mode": "BUS"},
        "agency": {"name": "JLT"},
        "trip": {"trip_id": f"trip_{line}_{minutes}", "start_date": "2026-11-08"},
        "stop": {"name": "Viktoriaplan"},
    }
    item.update(extra)
    return item


async def _setup(hass: HomeAssistant, data: dict, options: dict, payload: dict, enable: bool) -> str:
    entry = MockConfigEntry(domain=DOMAIN, data=data, options=options, unique_id=f"cal-{data['sensor_type']}-{enable}")
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    if enable:
        # Pre-register the entity as enabled, as a user enabling it would
        ent_reg.async_get_or_create(
            "calendar", DOMAIN, f"{entry.entry_id}_calendar", config_entry=entry, disabled_by=None
        )
    with patch(_UPDATE, return_value=payload):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    entity_id = ent_reg.async_get_entity_id("calendar", DOMAIN, f"{entry.entry_id}_calendar")
    assert entity_id is not None
    return entity_id


async def _events(hass: HomeAssistant, entity_id: str) -> list[dict]:
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "duration": {"hours": 3}},
        blocking=True,
        return_response=True,
    )
    return response[entity_id]["events"]


@pytest.mark.asyncio
async def test_calendar_disabled_by_default(hass: HomeAssistant) -> None:
    """The calendar entity is registered but disabled until the user enables it."""
    entity_id = await _setup(hass, ENTRY_DATA_DEPARTURE, ENTRY_OPTIONS_DEFAULT, {}, enable=False)
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


@pytest.mark.asyncio
async def test_calendar_departure_events(hass: HomeAssistant) -> None:
    """Departures become events in time order, honoring the entry's line filter."""
    payload = {
        "departures": [
            _departure("1", "Råslätt", 20, canceled=True),
            _departure("1", "Huskvarna", 5, delay=120),
            _departure("27", "Ekhagen", 10),
        ]
    }
    options = {**ENTRY_OPTIONS_DEFAULT, "line_filter": "1"}
    entity_id = await _setup(hass, ENTRY_DATA_DEPARTURE, options, payload, enable=True)

    events = await _events(hass, entity_id)
    assert [e["summary"] for e in events] == ["1 Huskvarna", "Canceled: 1 Råslätt"]
    first = events[0]
    assert first["location"] == "Viktoriaplan"
    assert "Platform: B" in first["description"]
    assert "Delay: 2 min" in first["description"]
    start = datetime.fromisoformat(first["start"])
    end = datetime.fromisoformat(first["end"])
    assert end - start == timedelta(minutes=1)
    assert start == _local(5).replace(tzinfo=_STOCKHOLM)

    state = hass.states.get(entity_id)
    assert state.attributes["message"] == "1 Huskvarna"


@pytest.mark.asyncio
async def test_calendar_resrobot_trip_spans_journey(hass: HomeAssistant) -> None:
    """A Resrobot trip becomes one event from first departure to final arrival."""
    dep = _local(15)
    arr = dep + timedelta(minutes=40)
    payload = {
        "Trip": [
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "Stop A", "date": f"{dep:%Y-%m-%d}", "time": f"{dep:%H:%M:%S}"},
                            "Destination": {"name": "Stop B", "date": f"{arr:%Y-%m-%d}", "time": f"{arr:%H:%M:%S}"},
                            "Product": {"name": "Buss 52", "num": "52"},
                            "category": "BLT",
                            "type": "JNY",
                            "duration": "PT40M",
                            "idx": 0,
                        }
                    ]
                }
            }
        ]
    }
    entity_id = await _setup(hass, ENTRY_DATA_RESROBOT, ENTRY_OPTIONS_RESROBOT, payload, enable=True)

    events = await _events(hass, entity_id)
    assert len(events) == 1
    event = events[0]
    assert event["summary"] == "Stop A → Stop B"
    assert datetime.fromisoformat(event["start"]) == dep.replace(tzinfo=_STOCKHOLM)
    assert datetime.fromisoformat(event["end"]) == arr.replace(tzinfo=_STOCKHOLM)
    assert "Buss 52 Stop A → Stop B" in event["description"]
