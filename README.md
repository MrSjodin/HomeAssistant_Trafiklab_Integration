# Home Assistant Trafiklab Integration

[![Stable](https://img.shields.io/badge/project%20state-stable-green.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration)
[![Maintained](https://img.shields.io/badge/maintained-yes-green.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration)
[![HACS](https://img.shields.io/badge/HACS-default-green.svg)](https://github.com/hacs/integration)
![Downloads](https://img.shields.io/github/downloads/MrSjodin/HomeAssistant_Trafiklab_Integration/total?color=blue)
[![Maintainer](https://img.shields.io/badge/maintainer-MrSjodin-blue.svg)](https://github.com/MrSjodin)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

**Trafiklab** Home Assistant custom integration for Swedish public transport, using the **Trafiklab Realtime API** and **Trafiklab Resrobot API**, presents you the timetables for a stop as well as the full route plan for your travel. The integration covers all major public transport operators in Sweden — not just SL. See [Operators](#operators) for the full list.

This integration is entirely community-developed and is not developed by, or in collaboration with, Trafiklab/Samtrafiken. Trafiklab/Samtrafiken has given the project a thumbs-up though — see [Trafiklab Praise page](https://support.trafiklab.se/org/trafiklabse/d/realtime-api-integrerat-i-home-assistant/).

## Contents

- [Features](#features)
- [Installation](#installation)
- [Finding Your Stop ID](#finding-your-stop-id)
- [Configuration](#configuration)
- [Sensors](#sensors)
- [Services](#services)
  - [Stop ID Lookup](#stop-id-lookup-service)
  - [Update Now](#update-now-service)
  - [Travel Search](#travel-search-service)
- [Automation Examples](#automation-examples)
- [Dashboard & Lovelace Cards](#dashboard--lovelace-cards)
- [Operators](#operators)
- [API Documentation](#api-documentation)

---

## Features

- **Real-time departures and arrivals**: Live departure and arrival information from any Trafiklab-covered stop in Sweden
- **Resrobot end-to-end travel search**: Trip planning between origin and destination (stop ID, coordinates, stop name, HA zone, or person entity)
- **Line filtering**: Monitor specific lines by filtering with comma-separated line numbers, per sensor
- **Destination filtering**: Filter by (substring) text match of destination(s) at a stop (useful for busy stops), per sensor
- **Configurable time window**: Set how many minutes ahead to search (1-1440 minutes), per sensor
- **Maximum trip duration filter**: For Travel Search sensors, exclude trips longer than a configurable limit (1-1440 minutes)
- **Transport mode filtering**: Filter by transport category — Bus, Metro, Train, Tram, or Boat/Ferry — for both Realtime and Travel Search sensors
- **Flexible sensor configuration**: Create separate sensors for departures and arrivals
- **Stop lookup service**: Find stop IDs by name using a Home Assistant service call
- **Update now service**: Force an immediate data refresh for one or all sensors — by service call or via the entry's button
- **Ad-hoc travel search service**: Query Resrobot for a journey on-demand without a permanent sensor, using stop IDs, coordinates, stop names, HA zones, or person/device_tracker entities
- **Config flow**: Easy setup through the Home Assistant UI
- **Multi-language support**: English and Swedish translations
- **Nationwide coverage**: All public transport operators in Sweden covered by Trafiklab


## Installation

### HACS (Recommended)

1. Search for "Trafiklab" in HACS
2. Install the integration
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/trafiklab` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Finding Your Stop ID

Before you can configure any sensor, you need the **stop ID** for your location. Use the built-in `trafiklab.stop_lookup` service to find it — see [Stop ID Lookup Service](#stop-id-lookup-service) for full details.

**Quick steps:**
1. If you have no Trafiklab config entries yet, add this one-line stub to `configuration.yaml` and restart:
   ```yaml
   trafiklab:
   ```
2. Open **Developer Tools → Services**, select `trafiklab.stop_lookup`
3. Enter your **Realtime API key** and a search string (your stop or town name)
4. Copy the `id` value from the response — that is your **Stop ID**

## Configuration

### Prerequisites

1. Get your API key(s) from [Trafiklab](https://www.trafiklab.se/) - it's free but please note that there are a default API quota with API call limitation.
2. Find the area/stop ID for your desired stop using the Stop Lookup service (see below)

Note about Resrobot: Trip planning uses Resrobot Travel Search which requires its own API key, requested from the same Trafiklab website where you request the Realtime API key. Make sure to activate/request both keys if you plan to use both sensor types.

### Setup

1. Go to Settings → Devices & Services → Add Integration → search for "Trafiklab".
2. Enter your Trafiklab API key and choose a sensor type:
   - Departures or Arrivals (Realtime)
   - Travel Search (end-to-end trip planning)
3. Enter a name (optional).
4. Fill in the fields for the chosen sensor type:
   - Departures/Arrivals:
     - Area/Stop ID (use the Stop Lookup service if needed)
     - Optional line filter and destination filter
     - Optional transport mode filter (Bus, Metro, Train, Tram, Boat/Ferry — leave empty for all)
     - Time window and refresh interval
     - Optional Update Condition (template)
   - Travel Search:
     - Origin and Destination: each can be a Stop ID or coordinates "lat,lon" (select type for each)
     - Optional via/avoid Stop IDs and maximum walking distance
     - Optional transport mode filter (Bus, Metro, Train, Tram, Boat/Ferry — leave empty for all)
     - Time window and refresh interval
     - Optional maximum trip duration (in minutes) — trips longer than this are excluded from results
5. Finish to create the sensor.

**Note**: The integration now uses **area IDs** from the Trafiklab Realtime API, which correspond to "rikshållplatser" (national stops) or meta-stops. Use the stop lookup service to find the correct area ID for your stop.

#### Refresh interval considerations
The refresh interval controls how often the integration fetches data from the Trafiklab API. Consider your API quota limits when setting this value. More frequent updates (lower values) consume more API calls. For example, if you have a departure sensor for a stop that updates every 5 minutes (300 seconds), that sensor alone will consume about 8.640 calls per month. Thus, you can have up to 11 departure or arrival sensors with 300 seconds update frequency to stay within the maximum initial quota. 

## Sensors


The integration creates sensors based on your configuration:

### Sensor Entity Naming

- **Entity ID format:**
  - Departure: `sensor.trafiklab_departure_[friendly_name_slug]`
  - Arrival: `sensor.trafiklab_arrival_[friendly_name_slug]`
  - Travel: `sensor.trafiklab_travel_[friendly_name_slug]`
  - Where `[friendly_name_slug]` is a slugified version of the name you configure in the UI.

### Departure Sensors (when sensor type is "Departures")
- **State**: Minutes until next departure (integer)
- **Unit**: Minutes
- **Device Class**: Duration
- **Attributes**: Detailed information about the next departure

### Arrival Sensors (when sensor type is "Arrivals")
- **State**: Minutes until next arrival (integer)
- **Unit**: Minutes
- **Device Class**: Duration
- **Attributes**: Detailed information about the next arrival

### Resrobot Travel Search Sensors (new in v0.6.0)
- **State**: Minutes until the first upcoming leg within the configured time window
- **Unit**: Minutes
- **Device Class**: Duration
- **Attributes**: Normalized list of trips and legs (origin/destination times, product, category, duration, etc.)

#### Maximum Trip Duration Filter (new in v0.7.0)

Travel Search sensors support an optional **Maximum Trip Duration** setting (1–1440 minutes). When set, any trip whose total travel time (first leg departure → last leg arrival) exceeds the limit is excluded from the `trips` attribute and cannot become the sensor state.

Leave the field empty (or set to `None`) for no limit. This is the default, so existing sensors without this option are fully backward compatible.

Each trip in the `trips` attribute now always includes a `duration_total` key (integer minutes, or `null` if times could not be parsed).

```yaml
# Example: only show trips shorter than 1 hour
options:
  max_trip_duration: 60
```


### Sensor Attributes

All sensors include comprehensive attributes for automation use:

#### Main Attributes
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

#### Travel Search Trips Array Structure

The `trips` attribute on Travel Search sensors contains a sorted array of trips, each with:

```json
{
  "index": 0,                           // Position in sorted list (0-based)
  "duration_total": 45,                 // Total trip duration in minutes (null if unparseable)
  "legs": [
    {
      "origin_name": "Stockholm C",     // Departure stop name
      "origin_time": "2025-08-08 14:30:00", // Departure date+time
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

#### Upcoming Departures/Arrivals Array Structure

The `upcoming` attribute contains an array of up to 10 upcoming departures/arrivals, each with:

```json
{
  "index": 0,                           // Position in list (0-based)
  "line": "7",                          // Line number/designation
  "destination": "Karolinska Institutet", // Where it's going
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
  "trip_id": "123456789"               // Unique trip identifier
}
```

### Configuration Examples

```yaml
# Example 1: All departures from a stop
- API Key: your_api_key
- Area ID: 740098000  # Stockholm meta-stop
- Name: Stockholm Central
- Sensor Type: Departures from this stop
- Line Filter: (empty - all lines)
- Direction: Both directions (will show direction: "2" in sensor attributes)
- Time Window: 60 minutes
- Refresh Interval: 300 seconds (default)

# Example 2: Only buses 1 and 4 departing in direction 1
- API Key: your_api_key
- Area ID: 740000002  # Göteborg Central
- Name: Bus Lines 1,4
- Sensor Type: Departures from this stop
- Line Filter: 1,4
- Direction: Direction 1 (will show direction: "0" in sensor attributes)
- Time Window: 30 minutes
- Refresh Interval: 120 seconds (more frequent updates)

# Example 3: All arrivals to a stop within 2 hours
- API Key: your_api_key
- Area ID: 740098000
- Name: Stockholm Arrivals
- Sensor Type: Arrivals to this stop
- Line Filter: (empty - all lines)
- Direction: Both directions (will show direction: "2" in sensor attributes)
- Time Window: 120 minutes
- Refresh Interval: 600 seconds (less frequent updates to save API quota)
```

**Destination Filter Explanation:**
You can enter any (part of) destination text (case-insensitive). Example: entering `central` will match destinations like "Stockholm Central" or "Centralstationen". Leave empty for all destinations.

**Transport Mode Filter Explanation:**
Select one or more transport categories to restrict which departures, arrivals, or trip legs are shown. Available modes:

| Mode | Covers |
|---|---|
| Bus | All bus services |
| Metro | Underground/subway (tunnelbana) |
| Train | Regional and commuter trains |
| Tram | Trams and light rail |
| Boat / Ferry | Ferries and boat services |

Leave the selection empty to include all modes (default behaviour, fully backward compatible with entries created before this setting existed).

> **Note for Travel Search sensors:** when a transport mode filter is set, legs that are not public transport (walk segments, transfer legs) are excluded from the displayed results, since they have no associated mode.

```yaml
# Example: only show bus and tram departures
options:
  transport_modes:
    - bus
    - tram
```

**Update Condition (Template) Explanation:**
You can provide a Home Assistant template which controls whether the integration performs an API request on each scheduled update. The template is evaluated in Home Assistant; if it renders to the literal string `true` (case-insensitive), the update proceeds. Otherwise, the API call is skipped and the last known data remains.

Examples:

```
{{ is_state('binary_sensor.workday_sensor', 'on') }}
```

```
{% if states('sensor.people_home')|int > 0 %}true{% else %}false{% endif %}
```

```
{% if now().hour >= 6 and now().hour <= 9 %}true{% endif %}
```

If the field is left empty, updates always occur. On template errors, the integration logs a warning and performs the update to avoid stale data.

**Sensor State Format:**
- Sensor state returns **integer minutes** until next departure/arrival
- Positive numbers indicate future departures (e.g., `15` = 15 minutes until departure)
- Zero indicates departure happening now
- Negative numbers indicate past departures (useful for detecting delays)
- `null`/`unavailable` indicates no data available

## Automation Examples

#### Basic Departure Notification
```yaml
automation:
  - alias: "Bus departure notification"
    trigger:
      - platform: numeric_state
        entity_id: sensor.trafiklab_departures_my_stop
        below: 6
        above: 4
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "Bus {{ state_attr('sensor.my_stop_next_departure', 'line') }} to {{ state_attr('sensor.my_stop_next_departure', 'destination') }} departing in {{ states('sensor.my_stop_next_departure') }} minutes!"
```

#### Check for Departures Soon
```yaml
automation:
  - alias: "Departures within 10 minutes"
    trigger:
      - platform: state
        entity_id: sensor.trafiklab_departures_my_stop
    condition:
      - condition: numeric_state
        entity_id: sensor.trafiklab_departures_my_stop
        below: 11
        above: 0
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "Next departure in {{ states('sensor.trafiklab_departures_my_stop') }} minutes"
```

#### Working with Upcoming Array - Line-Specific Automation
```yaml
automation:
  - alias: "Line 7 departures notification"
    trigger:
      - platform: time_pattern
        minutes: "/10"  # Every 10 minutes
    condition:
      # Check if line 7 is departing within 15 minutes
      - condition: template
        value_template: >
          {{ state_attr('sensor.trafiklab_departures_my_stop', 'upcoming') 
             | selectattr('line', 'eq', '7') 
             | selectattr('minutes_until', '<=', 15) 
             | list | count > 0 }}
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Line 7 departures in next 15 minutes:
            {% set line7_departures = state_attr('sensor.trafiklab_departures_my_stop', 'upcoming') 
               | selectattr('line', 'eq', '7') 
               | selectattr('minutes_until', '<=', 15) | list %}
            {% for departure in line7_departures %}
            {{ departure.time_formatted }} ({{ departure.minutes_until }} min){% if departure.delay_minutes > 0 %} - {{ departure.delay_minutes }}min delayed{% endif %}
            {% endfor %}
```

#### Delay Detection
```yaml
automation:
  - alias: "Delayed departures notification"
    trigger:
      - platform: state
        entity_id: sensor.trafiklab_departures_my_stop
        attribute: upcoming
    condition:
      # Check if any upcoming departure is delayed more than 5 minutes
      - condition: template
        value_template: >
          {{ state_attr('sensor.trafiklab_departures_my_stop', 'upcoming') 
             | selectattr('delay_minutes', '>', 5) 
             | list | count > 0 }}
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Delayed departures detected:
            {% set delayed = state_attr('sensor.trafiklab_departures_my_stop', 'upcoming') 
               | selectattr('delay_minutes', '>', 5) | list %}
            {% for departure in delayed %}
            Line {{ departure.line }} delayed {{ departure.delay_minutes }} minutes
            {% endfor %}
```

#### Platform-Specific Information
```yaml
automation:
  - alias: "Platform information"
    trigger:
      - platform: numeric_state
        entity_id: sensor.trafiklab_departures_my_stop
        below: 3
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.trafiklab_departures_my_stop', 'platform') != '' }}"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Next departure from platform {{ state_attr('sensor.trafiklab_departures_my_stop', 'platform') }} 
            in {{ states('sensor.my_stop_next_departure') }} minutes!
```

## Services

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

---

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
            {{ journey.trips[0].legs[0].origin_time }}.
```

---

## Dashboard & Lovelace Cards

There are companion dashboard cards designed for this integration:
- [Timetable card](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Timetable_Card) — shows upcoming departures/arrivals in a timetable layout
- [Travel Search card](https://github.com/MrSjodin/HomeAssistant_Trafiklab_TravelSearch_Card) — shows journey results from a Travel Search sensor

### Built-in Lovelace Card Examples

The sensors also work with any standard HA card. Some examples:

#### Basic Entity Card
```yaml
type: entities
title: Bus Departures
entities:
  - entity: sensor.trafiklab_departures_my_stop
    name: Next Departure
    secondary_info: >
      Line {{ state_attr('sensor.trafiklab_departures_my_stop', 'line') }} 
      to {{ state_attr('sensor.trafiklab_departures_my_stop', 'destination') }}
show_header_toggle: false
```

#### Custom Card with Upcoming Departures
```yaml
type: markdown
title: Upcoming Departures
content: |
  **Next Departure:** {{ states('sensor.trafiklab_departures_my_stop') }} minutes
  
  **Upcoming:**
  {% for departure in state_attr('sensor.trafiklab_departures_my_stop', 'upcoming')[:5] %}
  - Line **{{ departure.line }}** to {{ departure.destination }} 
    at {{ departure.time_formatted }} ({{ departure.minutes_until }} min)
    {% if departure.delay_minutes > 0 %}⚠️ {{ departure.delay_minutes }}min delayed{% endif %}
  {% endfor %}
```

#### Gauge Card for Minutes Until Departure
```yaml
type: gauge
entity: sensor.trafiklab_departures_my_stop
name: Minutes Until Departure
min: 0
max: 30
severity:
  green: 10
  yellow: 5
  red: 0
```

## Operators

The following operators are currently represented in the API:

### Static (timetable) data and realtime traffic data

- SL (Stockholm)
- UL (Uppsala)
- Östgötatrafiken
- JLT (Jönköping)
- Kronoberg
- KLT (Kalmar)
- Gotland
- Blekingetrafiken
- Skånetrafiken
- Värmlandstrafik
- Örebro, Länstrafiken
- Västmanland
- Dalatrafik
- X-trafik
- Din Tur - Västernorrland

### Static (timetable) data

- Sörmlandstrafiken
- Hallandstrafiken
- Västtrafik
- Jämtland
- Västerbotten
- Norrbotten
- BT buss
- Destination Gotland
- Falcks Omnibus AB
- Flixbus
- Härjedalingen
- Kiruna Buss
- Kombardo Expressen
- Lennakatten
- Luleå Lokaltrafik
- Masexpressen
- Mälartåg ersättningstrafik
- Nikkaluoktaexpressen
- Norrtåg ersättningsstrafik (VR Sverige)
- Ressel Rederi
- Roslagens sjötrafik
- Silverlinjen
- SJ
- SJ Norge
- Sjöstadstrafiken (Stockholm Stad)
- Skellefteåbuss
- Snälltåget
- Stavsnäs båttaxi
- Strömma Turism & Sjöfart AB
- TJF Smalspåret
- Trosabussen
- Tågab
- Uddevalla Skärgårdsbåtar AB
- VR
- Vy Bus4You
- Vy Flygbussarna
- Vy Norge
- Vy Tåg AB
- Vy Värmlandstrafik
- Y-Buss

For current list of operators, please visit [Trafiklab Timetables page](https://www.trafiklab.se/sv/api/our-apis/trafiklab-realtime-apis/timetables/)

## API Documentation

This integration uses the following Trafiklab APIs and endpoints:

- [Trafiklab Realtime APIs](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/) — departures, arrivals, and stop lookup
- [Trafiklab Timetables](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/timetables/) — departure and arrival boards
- [Trafiklab Stop Lookup](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/stop-lookup/) — finding stops by name (used by the `stop_lookup` service)
- [Resrobot v2.1 Travel Search](https://www.trafiklab.se/api/our-apis/resrobot-v21/) — trip planning between any two points in Sweden (used by Travel Search sensors and the `travel_search` service; requires a separate Resrobot API key)
- [Resrobot v2.1 Stop Lookup](https://www.trafiklab.se/api/our-apis/resrobot-v21/stop-lookup/) — stop name resolution returning national stop IDs (used internally by the `travel_search` service when `origin_type` or `destination_type` is `"name"`)


## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License - see the [LICENSE](LICENSE) file for details.

## Support

- [Report Issues](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues)
- [Trafiklab API Documentation](https://www.trafiklab.se/api/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)

## Updates, todo's/roadmap, issues and feature requests

Developing isn't my day job - I'm taking care of this integration solely on my free time. This means that I most probably won't try the integration out in pre-releases of Home Assistant updates. Thus, it might break in the .0 versions of Home Assistant releases before I'm able to take care of it. Feel free to contribute though!

- [Feature Request (mark as "FR")](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues)
- [Report Issues](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues)
- [Trafiklab API Documentation](https://www.trafiklab.se/api/)

## Acknowledgments

- [Trafiklab](https://www.trafiklab.se/) for providing the excellent public transport API
- Home Assistant community for excellent development documentation
- [HASL developers](https://github.com/hasl-sensor/) for the integration that basically provided the idea behind this integration
- Claude Sonnet & friends, for being quite helpful sort things out whenever I'm a little out on the deep waters... Like I said - developing isn't my day job 
