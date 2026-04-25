# Trafiklab Integration — Copilot Instructions

## Project Overview

Home Assistant custom integration for Swedish public transport via the Trafiklab APIs.
Two sensor types: **Realtime departures/arrivals** (Trafiklab Realtime API) and **end-to-end trip planning** (Resrobot v2.1).

## Key References

| Topic | URL |
|---|---|
| HA custom component development | https://developers.home-assistant.io/docs/creating_integration_manifest |
| HA config flow | https://developers.home-assistant.io/docs/config_entries_config_flow_handler |
| HA entity model | https://developers.home-assistant.io/docs/core/entity |
| HA CoordinatorEntity | https://developers.home-assistant.io/docs/integration_fetching_data |
| Trafiklab Realtime API spec | https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/openapi-specification/ |
| Resrobot v2.1 API spec | https://www.trafiklab.se/api/our-apis/resrobot-v21/api-spec/ |

## Architecture

```
custom_components/trafiklab/
  __init__.py          # Entry setup/unload, service registration
  api.py               # TrafikLabApiClient — all HTTP calls
  config_flow.py       # ConfigFlow + OptionsFlowHandler (voluptuous schemas)
  coordinator.py       # TrafikLabCoordinator (DataUpdateCoordinator subclass)
  sensor.py            # TrafikLabSensor entity + _normalize_resrobot_trips()
  const.py             # All CONF_* and SENSOR_TYPE_* constants — add here first
  diagnostics.py       # async_get_config_entry_diagnostics
  services_setup.py    # Stop lookup service
```

## Conventions

### Constants
All config/option keys live in `const.py` as `Final` strings. Import them everywhere; never use raw string literals for key names.

### Config & Options
- `entry.data` — set at creation, rarely changes (API key, stop IDs, sensor type)
- `entry.options` — user-editable after setup (filters, time window, etc.)
- Always merge with `{**entry.options, **entry.data}` when reading (options override data for shared keys is intentional here — data provides defaults, options take precedence).
- Use `options.get(KEY)` (not `options[KEY]`) for optional fields; absence and `None` are both "not set".

### Voluptuous schemas
Nullable integer fields follow this pattern:
```python
vol.Optional(CONF_MAX_TRIP_DURATION, default=None): vol.Any(
    None, vol.All(vol.Coerce(int), vol.Range(min=1, max=1440))
)
```

### Sensor types
- `"departure"` — Realtime departures  
- `"arrival"` — Realtime arrivals  
- `"resrobot_travel_search"` — Resrobot trip planning  
Only `resrobot_travel_search` uses `_normalize_resrobot_trips()`.

### Backward compatibility
New optional config keys must use `.get(KEY)` returning `None` when absent so old config entries without the key work without migration.

### Translations
Both `translations/en.json` and `translations/sv.json` must be updated together whenever a new config/options field is added.

## Build & Test

```bash
pip install -r requirements-dev.txt
pytest tests/ --cov=custom_components.trafiklab --cov-report=xml
```

Tests run on **Ubuntu / Python 3.11** in CI (`.github/workflows/validate.yaml`). Do not target Python 3.13 or Windows-specific wheels.

### Test conventions
- Framework: `pytest` + `pytest-homeassistant-custom-component` + `asyncio_mode = "auto"`
- All test modules carry `pytestmark = pytest.mark.usefixtures("enable_custom_integrations")`
- Use `MockConfigEntry` + `hass.config_entries.async_setup()` to set up sensors in tests
- Mock API calls with `unittest.mock.patch` on `TrafikLabApiClient` methods
- Resrobot test fixtures use `date="2099-12-31"` so `native_value` is `None` (beyond time window) while `extra_state_attributes["trips"]` is still populated — assert on attributes, not state value
- Shared fixtures live in `tests/components/trafiklab/conftest.py`

## Resrobot Trip Normalisation

`_normalize_resrobot_trips(trips_raw, max_trip_duration)` in `sensor.py`:
- Parses `Trip[].LegList.Leg[]` from the Resrobot response
- Computes `duration_total` (int minutes, first leg departure → last leg arrival; `None` if times unparseable)
- Filters out trips where `duration_total > max_trip_duration` (skipped when `max_trip_duration is None`)
- Returns trips sorted by first-leg departure time with sequential `index` values
- Trips with `duration_total = None` are **never** filtered out (unparseable times are not penalised)
