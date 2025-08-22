from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab import async_migrate_entry
from custom_components.trafiklab.const import DOMAIN


@pytest.mark.asyncio
async def test_migrate_entry_v1_to_v2_moves_options(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "k",
            "stop_id": "740098000",
            "name": "X",
            "sensor_type": "departure",
            "line_filter": "52",
            "direction": "Cent",
            "time_window": 60,
            "refresh_interval": 300,
        },
        options={},
        version=1,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is True
    assert entry.version == 2
    # Keys moved to options
    assert "line_filter" not in entry.data
    assert entry.options.get("line_filter") == "52"
    assert entry.options.get("direction") == "Cent"
    assert entry.options.get("time_window") == 60
    assert entry.options.get("refresh_interval") == 300
