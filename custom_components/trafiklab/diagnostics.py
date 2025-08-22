"""Diagnostics support for Trafiklab integration.

Follows Home Assistant diagnostics guidelines:
- Redact secrets (API keys) using async_redact_data
- Avoid including large/raw payloads; provide shapes/keys instead
- Include integration and HA version metadata
"""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.loader import async_get_integration

from .api import TrafikLabApiClient, TrafikLabApiError
from .const import CONF_API_KEY, CONF_STOP_ID, DOMAIN

# Keys to redact from diagnostics data for privacy
TO_REDACT = {
    CONF_API_KEY,
    "api_key",
    "key",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    # Resolve integration metadata (version from manifest)
    try:
        integration = await async_get_integration(hass, DOMAIN)
        integration_version = integration.version
    except Exception:  # pragma: no cover - fallback safety
        integration_version = None
    
    # Basic integration info
    diagnostics_data = {
    "integration_version": integration_version,
    "home_assistant_version": HA_VERSION,
        "config_entry": {
            "title": entry.title,
            "domain": entry.domain,
            "version": entry.version,
            "source": entry.source,
            "state": entry.state.value,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
            "unique_id": entry.unique_id,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception) if coordinator.last_exception else None,
            "update_interval": str(coordinator.update_interval),
            "data_available": coordinator.data is not None,
        },
        "entities": {},
        "api_test": {},
    }
    
    # Add coordinator data (if available and not sensitive)
    if coordinator.data:
        # Redact any sensitive data from coordinator data
        coordinator_data = coordinator.data
        if isinstance(coordinator_data, dict):
            diagnostics_data["coordinator"]["sample_data_keys"] = list(coordinator_data.keys())
            # Add sample data structure without actual values
            if "departures" in coordinator_data:
                departures = coordinator_data["departures"]
                if isinstance(departures, list) and departures:
                    sample_departure = departures[0]
                    if isinstance(sample_departure, dict):
                        diagnostics_data["coordinator"]["sample_departure_structure"] = list(sample_departure.keys())
        else:
            diagnostics_data["coordinator"]["data_type"] = type(coordinator_data).__name__
    
    # Collect entity information
    for state in hass.states.async_all():
        if (state.domain == "sensor" and 
            hasattr(state, "attributes") and 
            state.attributes.get("integration") == DOMAIN):
            
            entity_data = {
                "state": state.state,
                "attributes": async_redact_data(dict(state.attributes), TO_REDACT),
                "last_changed": state.last_changed.isoformat() if state.last_changed else None,
                "last_updated": state.last_updated.isoformat() if state.last_updated else None,
                "context_id": state.context.id if state.context else None,
            }
            diagnostics_data["entities"][state.entity_id] = entity_data
    
    # Perform API connectivity test
    if entry.data.get(CONF_API_KEY) and entry.data.get(CONF_STOP_ID):
        api_key = entry.data[CONF_API_KEY]
        stop_id = entry.data[CONF_STOP_ID]
        
        try:
            async with TrafikLabApiClient(api_key) as client:
                # Test API connectivity
                start_time = asyncio.get_event_loop().time()
                result = await client.get_departures(stop_id)
                end_time = asyncio.get_event_loop().time()
                
                response_time = round((end_time - start_time) * 1000, 2)  # Convert to milliseconds
                
                diagnostics_data["api_test"] = {
                    "success": True,
                    "response_time_ms": response_time,
                    "response_structure": {
                        "is_dict": isinstance(result, dict),
                        "keys": list(result.keys()) if isinstance(result, dict) else "not_dict",
                        "data_size": len(str(result)),
                    },
                    "endpoint_tested": f"departures/{stop_id}",
                }
                
                # Add additional structure information if it's a dict
                if isinstance(result, dict):
                    for key, value in result.items():
                        if isinstance(value, list):
                            diagnostics_data["api_test"]["response_structure"][f"{key}_count"] = len(value)
                            if value and isinstance(value[0], dict):
                                diagnostics_data["api_test"]["response_structure"][f"{key}_sample_keys"] = list(value[0].keys())
                        elif isinstance(value, dict):
                            diagnostics_data["api_test"]["response_structure"][f"{key}_keys"] = list(value.keys())
                
        except TrafikLabApiError as err:
            diagnostics_data["api_test"] = {
                "success": False,
                "error": str(err),
                "error_type": "TrafikLabApiError",
                "endpoint_tested": f"departures/{stop_id}",
            }
        except Exception as err:
            diagnostics_data["api_test"] = {
                "success": False,
                "error": str(err),
                "error_type": type(err).__name__,
                "endpoint_tested": f"departures/{stop_id}",
            }
    else:
        diagnostics_data["api_test"] = {
            "success": False,
            "error": "Missing API key or stop ID in configuration",
            "endpoint_tested": "none",
        }
    
    return diagnostics_data
