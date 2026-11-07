from __future__ import annotations
# pyright: reportMissingImports=false, reportGeneralTypeIssues=false

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.trafiklab import async_migrate_entry
from custom_components.trafiklab.const import DOMAIN


@pytest.mark.asyncio
async def test_migrate_entry_v1_to_v3_moves_options(hass: HomeAssistant) -> None:
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
    assert entry.version == 3
    # Keys moved to options
    assert "line_filter" not in entry.data
    assert entry.options.get("line_filter") == "52"
    assert entry.options.get("direction") == "Cent"
    assert entry.options.get("time_window") == 60
    assert entry.options.get("refresh_interval") == 300


@pytest.mark.asyncio
async def test_migrate_entry_v1_to_v3_persists_version_without_data_changes(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "k",
            "stop_id": "740098000",
            "name": "X",
            "sensor_type": "departure",
        },
        options={"transport_modes": []},
        version=1,
    )
    entry.add_to_hass(hass)

    with patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    ) as mock_update_entry:
        ok = await async_migrate_entry(hass, entry)

    assert ok is True
    assert entry.version == 3
    mock_update_entry.assert_called_once_with(
        entry,
        data=entry.data,
        options=entry.options,
        version=3,
    )


@pytest.mark.asyncio
async def test_migrate_entry_v1_to_v3_caps_time_window_above_60(hass: HomeAssistant) -> None:
    """A v1 entry with a time_window above 60 must end up capped to 60 after migrating to v3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "k",
            "stop_id": "740098000",
            "name": "X",
            "sensor_type": "departure",
            "time_window": 180,
        },
        options={},
        version=1,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is True
    assert entry.version == 3
    assert entry.options.get("time_window") == 60

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, f"time_window_capped_{entry.entry_id}") is not None


@pytest.mark.asyncio
async def test_migrate_entry_v2_to_v3_caps_time_window_above_60(hass: HomeAssistant) -> None:
    """A v2 entry (time_window already in options) above 60 must be capped to 60 on migration to v3."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "arrival"},
        options={"time_window": 240, "refresh_interval": 300},
        version=2,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is True
    assert entry.version == 3
    assert entry.options.get("time_window") == 60

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, f"time_window_capped_{entry.entry_id}") is not None


@pytest.mark.asyncio
async def test_migrate_entry_v2_to_v3_leaves_time_window_at_or_below_60_unchanged(hass: HomeAssistant) -> None:
    """A v2 entry with time_window already <= 60 must be migrated without being touched or flagged."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"api_key": "k", "stop_id": "740098000", "name": "X", "sensor_type": "departure"},
        options={"time_window": 60, "refresh_interval": 300},
        version=2,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is True
    assert entry.version == 3
    assert entry.options.get("time_window") == 60

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, f"time_window_capped_{entry.entry_id}") is None


@pytest.mark.asyncio
async def test_migrate_entry_v2_to_v3_does_not_cap_resrobot_time_window(hass: HomeAssistant) -> None:
    """Resrobot sensors are unaffected: their time_window never drives extra API calls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "k",
            "name": "Travel",
            "sensor_type": "resrobot_travel_search",
            "origin_type": "stop_id",
            "origin": "740000001",
            "destination_type": "stop_id",
            "destination": "740000002",
        },
        options={"time_window": 180, "refresh_interval": 300},
        version=2,
    )
    entry.add_to_hass(hass)

    ok = await async_migrate_entry(hass, entry)
    assert ok is True
    assert entry.version == 3
    assert entry.options.get("time_window") == 180

    issue_reg = ir.async_get(hass)
    assert issue_reg.async_get_issue(DOMAIN, f"time_window_capped_{entry.entry_id}") is None
