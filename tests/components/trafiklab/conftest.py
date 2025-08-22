from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab.const import DOMAIN


@pytest.fixture
async def setup_integration(hass: HomeAssistant, enable_custom_integrations: None) -> bool:
    """Ensure domain setup runs to register services."""
    assert await async_setup_component(hass, DOMAIN, {DOMAIN: {}})
    await hass.async_block_till_done()
    return True


@pytest.fixture
def mock_departures_response() -> dict[str, Any]:
    return {
        "timestamp": "2025-01-01T12:00:00+00:00",
        "query": {},
        "stops": [],
        "departures": [
            {
                "scheduled": "2025-01-01T12:05:00+00:00",
                "realtime": "2025-01-01T12:06:00+00:00",
                "is_realtime": True,
                "delay": 60,
                "realtime_platform": {"designation": "1"},
                "route": {
                    "designation": "52",
                    "direction": "Central Station",
                    "transport_mode": "BUS",
                },
            }
        ],
    }


@pytest.fixture
def mock_arrivals_response() -> dict[str, Any]:
    return {
        "timestamp": "2025-01-01T12:00:00+00:00",
        "query": {},
        "stops": [],
        "arrivals": [
            {
                "scheduled": "2025-01-01T12:05:00+00:00",
                "realtime": "2025-01-01T12:06:00+00:00",
                "is_realtime": True,
                "delay": 60,
                "realtime_platform": {"designation": "1"},
                "route": {
                    "designation": "52",
                    "direction": "Central Station",
                    "transport_mode": "BUS",
                },
            }
        ],
    }


@pytest.fixture
def mock_resrobot_response() -> dict[str, Any]:
    # Minimal structure containing one Trip with a LegList.Leg entry
    return {
        "Trip": [
            {
                "LegList": {
                    "Leg": [
                        {
                            "Origin": {"name": "Stop A", "date": "2025-01-01", "time": "12:10:00"},
                            "Destination": {"name": "Stop B", "date": "2025-01-01", "time": "12:30:00"},
                            "Product": {"name": "Bus 52", "catOutL": "Bus", "num": "52"},
                            "category": "BUS",
                            "duration": "PT20M",
                            "direction": "Central Station",
                            "idx": 1,
                        }
                    ]
                }
            }
        ]
    }


@pytest.fixture
def mock_config_entry_factory():
    """Factory to create and add MockConfigEntry instances."""

    def _factory(hass: HomeAssistant, data: dict[str, Any], options: dict[str, Any] | None = None) -> MockConfigEntry:
        entry = MockConfigEntry(domain=DOMAIN, data=data, options=options or {}, unique_id="test-unique")
        entry.add_to_hass(hass)
        return entry

    return _factory
