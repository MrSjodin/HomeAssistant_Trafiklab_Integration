# Trafiklab Home Assistant Integration — Sensor & Service Reference

[← Back to the main README](../README.md)

Full attribute schemas for every sensor type, and complete request/response examples for all four services (`travel_search`, `update_now`, `stop_lookup`, `trip_details`).

## Sensor Entity Naming

- **Entity ID format:**
  - Departure: `sensor.trafiklab_departure_[friendly_name_slug]`
  - Arrival: `sensor.trafiklab_arrival_[friendly_name_slug]`
  - Travel: `sensor.trafiklab_travel_[friendly_name_slug]`
  - Where `[friendly_name_slug]` is a slugified version of the name you configure in the UI.

## Departure Sensors (when sensor type is "Departures")
- **State**: Minutes until next departure (integer)
- **Unit**: Minutes
- **Device Class**: Duration
- **Attributes**: Detailed information about the next departure

## Arrival Sensors (when sensor type is "Arrivals")
- **State**: Minutes until next arrival (integer)
- **Unit**: Minutes
- **Device Class**: Duration
- **Attributes**: Detailed information about the next arrival

## Resrobot Travel Search Sensors
- **State**: Minutes until the first upcoming leg within the configured time window
- **Unit**: Minutes
- **Device Class**: Duration
- **Attributes**: Normalized list of trips and legs (origin/destination times, product, category, duration, etc.)

### Maximum Trip Duration Filter

Travel Search sensors support an optional **Maximum Trip Duration** setting (1–1440 minutes). When set, any trip whose total travel time (first leg departure → last leg arrival) exceeds the limit is excluded from the `trips` attribute and cannot become the sensor state.

Leave the field empty (or set to `None`) for no limit. This is the default, so existing sensors without this option are fully backward compatible.

Each trip in the `trips` attribute now always includes a `duration_total` key (integer minutes, or `null` if times could not be parsed).

```yaml
# Example: only show trips shorter than 1 hour
options:
  max_trip_duration: 60
```

### Maximum Number of Results

Both Departure/Arrival sensors and Travel Search sensors support an optional **Maximum Number of Results** setting (1–100), configurable through the config flow (initial setup) or the options flow (reconfigure). It controls how many items are exposed in the `upcoming` attribute (Departure/Arrival) or the `trips` attribute (Travel Search).

If left unset, it defaults to **10**, matching the previous hardcoded behavior — fully backward compatible with existing sensors.

```yaml
# Example: return up to 25 trips/departures instead of the default 10
options:
  max_results: 25
```

### Realtime Delay Cross-Check

Travel Search sensors and the `trafiklab.travel_search` service support realtime cross-checking for each public-transport leg against the Trafiklab Realtime Timetable API — the same cross-check used internally by Departure/Arrival sensors. It resolves each leg's platform, delay, cancellation status, and updated (realtime) departure time.

For a Travel Search sensor, enable the **Include platform** option (`include_platform`). A configured Departure or Arrival sensor is required so its Realtime API key can be reused automatically. For the `trafiklab.travel_search` service, pass `include_platform: true`; provide `realtime_api_key` explicitly or let the service reuse the key from a configured Departure or Arrival sensor. If no Realtime API key is available, the service returns the scheduled-time fallback values. One extra API call is made per unique origin stop on each sensor refresh or service call.

When enabled:
- Each leg gains `platform`, `expected_time`, `real_time`, `delay`, and `canceled` fields in the sensor attributes or service response (see [Travel Search Trips Array Structure](#travel-search-trips-array-structure)). `origin_time` remains the scheduled departure; use `expected_time` for the realtime-adjusted departure. When no realtime match is available, `expected_time` falls back to `origin_time` and `real_time` is `false`.
- The sensor's minutes-until-departure state, and the time-window filter, use the realtime-adjusted time instead of the static timetable time, so delays are reflected in the countdown.

```yaml
options:
  include_platform: true
```

## Sensor Attributes

All sensors include comprehensive attributes for automation use:

### Main Attributes
- `line`: Line number/designation (e.g., "7", "42X")
- `destination`: Where the vehicle is heading
- `direction`: User-configured direction filter ("0", "1", or "")
- `scheduled_time`: Original scheduled departure/arrival time (ISO format)
- `expected_time`: Real-time expected time (ISO format) 
- `transport_mode`: Type of transport (BUS, TRAIN, METRO, TRAM, BOAT)
- `real_time`: Boolean indicating if real-time data is available
- `delay`: Delay in seconds (integer)
- `canceled`: Boolean indicating if canceled
- `platform`: Platform or stop position
- `upcoming`: Array of upcoming departures/arrivals (see structure below)
- `trips`: (Travel Search only) Array of upcoming trips — see structure below

### Travel Search Trips Array Structure

The `trips` attribute on Travel Search sensors contains a sorted array of trips, each with:

```json
{
  "index": 0,                           // Position in sorted list (0-based)
  "duration_total": 45,                 // Total trip duration in minutes (null if unparseable)
  "legs": [
    {
      "origin_name": "Stockholm C",     // Departure stop name
      "origin_time": "2025-08-08 14:30:00", // Scheduled departure date+time
      "expected_time": "2025-08-08 14:32:00", // Realtime-adjusted departure time (requires include_platform; falls back to origin_time)
      "real_time": true,                 // Whether realtime data was found for this leg (requires include_platform)
      "delay": 120,                       // Delay in seconds (requires include_platform)
      "canceled": false,                  // Whether this departure is canceled (requires include_platform)
      "platform": "3",                    // Departure platform (requires include_platform)
      "dest_name": "Uppsala C",         // Arrival stop name
      "dest_time": "2025-08-08 15:15:00",   // Arrival date+time
      "type": "Public Transport",        // Leg type (Public Transport / Transfer / Walk to/from)
      "product": "SJ Regional",          // Product/service name
      "direction": "Uppsala",            // Headsign/direction
      "line_number": "42",               // Line number
      "category": "Train",               // Translated transport category
      "duration": 45                     // Leg duration in minutes
    }
  ]
}
```

### Upcoming Departures/Arrivals Array Structure

The `upcoming` attribute contains an array of upcoming departures/arrivals, limited by the configurable **Maximum Number of Results** option (default 10), each with:

```json
{
  "index": 0,                           // Position in list (0-based)
  "line": "7",                          // Line number/designation
  "destination": "Karolinska Institutet", // Displayed direction/headsign
  "origin": "Kungsplan",                  // First stop on the route
  "final_destination": "Olofströms resecentrum", // Last stop on the route
  "direction": "1",                     // User-configured direction filter
  "scheduled_time": "2025-08-08T14:30:00", // Raw scheduled time
  "expected_time": "2025-08-08T14:32:00",  // Raw real-time
  "time_formatted": "14:32",            // Human-readable HH:MM
  "minutes_until": 15,                  // Integer minutes until departure
  "transport_mode": "BUS",              // Transport type
  "real_time": true,                    // Has real-time data
  "delay": 120,                         // Delay in seconds
  "delay_minutes": 2,                   // Delay in minutes
  "canceled": false,                    // Is canceled
  "platform": "A",                     // Platform/stop position
  "route_name": "Blå linjen",          // Route name if available
  "agency": "SL",                       // Transport agency
  "trip_id": "123456789",                // Unique trip identifier
  "trip_start_date": "2026-09-25"         // Scheduled start date; pair with trip_id for trip lookup
}
```

## Services

### Travel Search Service

Query Resrobot for a journey on demand — no permanent sensor required. Returns normalised trips directly as a service response. Requires a **Resrobot API key** (separate from the Realtime key).

The `api_key` is optional when you already have a Resrobot Travel Search sensor configured; the key is resolved automatically from it.

#### Origin and destination types

| `origin_type` / `destination_type` | `origin` / `destination` value | Notes |
|---|---|---|
| `stop_id` *(default)* | National stop ID, e.g. `"740000001"` | Use Stop Lookup to find IDs |
| `coordinates` | `"lat,lon"`, e.g. `"59.330,18.059"` | Decimal degrees |
| `name` | Free-text stop name, e.g. `"Stockholm C"` | First Resrobot match is used; resolved ID returned as `resolved_origin_id` / `resolved_destination_id` |
| `zone` | HA zone name or entity ID, e.g. `"home"` or `"zone.work"` | Resolved coordinates returned as `resolved_origin_coords` / `resolved_destination_coords` |
| `person` | HA person or device_tracker entity ID, e.g. `"person.john"` | Uses GPS attributes when available; falls back to the zone the person is currently in |

#### Basic example — two stop IDs

```yaml
service: trafiklab.travel_search
data:
  origin: "740000001"
  destination: "740098000"
```

#### Name resolution

```yaml
service: trafiklab.travel_search
data:
  origin: "Centralen"
  origin_type: "name"
  destination: "Odenplan"
  destination_type: "name"
```

The response includes `resolved_origin_id` and `resolved_destination_id` with the national stop IDs that were used.

#### Using a zone as destination

```yaml
service: trafiklab.travel_search
data:
  origin: "740000001"
  destination: "home"         # resolves zone.home
  destination_type: "zone"
```

Response includes `resolved_destination_coords`.

#### Using current position as origin

```yaml
service: trafiklab.travel_search
data:
  origin: "person.john"      # uses GPS or falls back to zone coords
  origin_type: "person"
  destination: "740098000"
```

#### Full example with all options

```yaml
service: trafiklab.travel_search
data:
  api_key: "your_resrobot_api_key"   # optional — resolved from Resrobot sensor if omitted
  origin: "person.john"
  origin_type: "person"
  destination: "home"
  destination_type: "zone"
  via: "740001234"                   # optional intermediate stop
  max_walking_distance: 800          # metres (default 1000)
  transport_modes:                   # empty = all modes
    - train
    - bus
  max_trip_duration: 90              # exclude trips longer than 90 minutes
  include_platform: true              # include realtime leg data
  realtime_api_key: "your_realtime_api_key"  # optional if a Departure/Arrival sensor is configured
```

#### Service response

```yaml
total_trips: 2
resolved_origin_coords: "59.340,18.055"   # present when origin_type is person or zone
resolved_destination_coords: "59.329,18.068"
trips:
  - index: 0
    duration_total: 42          # total minutes, null if times unparseable
    legs:
      - origin_name: "Nearest stop"
        origin_time: "2026-05-03 14:30:00"
        expected_time: "2026-05-03 14:32:00"  # realtime departure; falls back to origin_time
        real_time: true                       # false when realtime data was not found
        delay: 120                            # seconds; 0 when unavailable
        canceled: false
        platform: "3"
        dest_name: "Stockholm C"
        dest_time: "2026-05-03 15:00:00"
        type: "Public Transport"
        product: "SJ Regional"
        direction: "Stockholm"
        line_number: "42"
        category: "Train"
        duration: 30
  - index: 1
    duration_total: 55
    legs: [ ... ]
```

If an error occurs (bad API key, unresolvable stop name, etc.) the response contains `trips: []`, `total_trips: 0`, and an `error` field with a description.

---

### Update Now Service

Force an immediate data refresh for one or all configured sensors. Useful in automations that react to events (arrivals home, alarm clock, etc.) and need fresh data right away.

```yaml
# Refresh all Trafiklab sensors at once
service: trafiklab.update_now
```

```yaml
# Refresh a single sensor by its config entry ID
service: trafiklab.update_now
data:
  config_entry_id: "your_entry_id"
```

The `config_entry_id` is shown in **Settings → Devices & Services → Trafiklab → (entry) → Info**. Omit it to refresh every active Trafiklab entry.

#### Automation example

```yaml
automation:
  - alias: "Refresh departures when arriving home"
    trigger:
      - platform: state
        entity_id: person.john
        to: "home"
    action:
      - service: trafiklab.update_now
```

#### Automation example — notify on journey options

```yaml
automation:
  - alias: "Journey home options"
    trigger:
      - platform: time
        at: "16:00:00"
    action:
      - service: trafiklab.travel_search
        data:
          origin: "person.john"
          origin_type: "person"
          destination: "home"
          destination_type: "zone"
          max_trip_duration: 60
        response_variable: journey
      - condition: template
        value_template: "{{ journey.total_trips > 0 }}"
      - service: notify.mobile_app_my_phone
        data:
          message: >
            {{ journey.total_trips }} journey(s) home found.
            Next departs at
            {{ journey.trips[0].legs[0].expected_time }}.
```

---

### Stop ID Lookup Service

Before you can configure a departure, arrival, or travel search sensor you need the **stop ID** for your location. The `trafiklab.stop_lookup` service lets you find it directly from Home Assistant without leaving the UI.

#### Getting started — before your first sensor

The service registers as soon as the integration is loaded. If you haven't added any Trafiklab config entry yet, add a one-line YAML stub so the integration loads on startup:

```yaml
# configuration.yaml
trafiklab:
```

Restart Home Assistant, then open **Developer Tools → Services**, search for `trafiklab.stop_lookup`, and call it with your Realtime API key and a search string.

#### Calling the service

```yaml
service: trafiklab.stop_lookup
data:
  api_key: "your_realtime_api_key"  # required the first time; optional once a departure/arrival sensor exists
  search_query: "Stockholm"
```

**`api_key`** is your [Trafiklab Realtime API key](https://www.trafiklab.se/). Once you have at least one departure or arrival sensor configured, the key is resolved automatically and you can omit this field entirely.

#### Response

```yaml
search_query: "Stockholm"
total_stops: 3
stops_found:
  - id: "740098000"     # ← copy this value as the Stop ID when setting up a sensor
    name: "Stockholm"
    area_type: "META_STOP"
    transport_modes: ["BUS", "TRAIN", "TRAM", "METRO"]
    average_daily_departures: 3198.92
    child_stops:
      - id: "1"
        name: "Stockholm Centralstation"
        lat: 59.331537
        lon: 18.054943
```

Use the `id` value from `stops_found` as the **Stop ID** (or **Origin / Destination** for Travel Search) when creating a sensor. The area-level ID (e.g. `740098000`) covers all platforms at that location and is usually what you want.

> **Tip:** If your search returns many results, add more of the stop name to narrow it down — e.g. `"Stockholms centralstation"` instead of `"Stockholm"`.

---

### Trip Details Service

Look up the complete route for one departure or arrival on demand. Use the `trip_id` and `trip_start_date` attributes exposed by an upcoming sensor; pass `trip_start_date` to the service as `start_date`. The service does not add trip-detail requests to regular sensor updates.

```yaml
service: trafiklab.trip_details
data:
  trip_id: "121120000398892276"
  start_date: "2026-09-26"
```

The service returns route summary fields (`line`, `transport_mode`, `headsign`, `origin`, and `destination`) alongside the original Trafiklab response and its full `calls` list. Each call includes the available scheduled and realtime arrivals/departures, stop, platforms, alerts, cancellation state, and realtime status. An `api_key` may be supplied explicitly; otherwise the service uses the selected `config_entry_id` or an available Departure/Arrival sensor's Realtime key.

**Note:** Trafiklab Trips API is currently in beta - it might change without further notice causing this service to fail. If you find it to fail, please create an issue (or contribute with changes needed).
