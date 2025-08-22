# Home Assistant Trafiklab Integration

[![Testing](https://img.shields.io/badge/project%20state-testing-yellow.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration)
[![Maintained](https://img.shields.io/badge/maintained-yes-brightgreen.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration)
[![HACS](https://img.shields.io/badge/HACS-default-brightgreen.svg)](https://github.com/hacs/integration)
[![Maintainer](https://img.shields.io/badge/maintainer-MrSjodin-blue.svg)](https://github.com/MrSjodin)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

So, here's a hopefully useful Home Assistant custom integration for Swedish public transport information by using the newer **Trafiklab Realtime API**.

The story behind is that I'd like to be able to show the upcoming departures from our nearest stops in the Home Assistant ecosystem, a bit outside of the city (and not in the SL area). Although HASL is a great integration, the newer versions only supports SL - therefore I saw a need to have a native integration towards the **Trafiklab Realtime API** for use in more or less the whole country.

For a complete list of traffic operators covered by the API and this integration, see [Operators](#operators) section below. 

This integration has not been developed by, or in collaboration with, Trafiklab/Samtrafiken but is entirely community-developed. Trafiklab/Samtrafiken has been informed about the integration and has given the project a thumbs-up regarding the use of their API, etc. See [Trafiklab Praise page](https://support.trafiklab.se/org/trafiklabse/d/realtime-api-integrerat-i-home-assistant/) as reference.

## API and Integration Features

- **Real-time departures and arrivals**: Get live realtime departure and arrival information from any Trafiklab covered stop in Sweden
- **Resrobot end-to-end travel search (new in v0.6.0)**: Trip planning between origin and destination (stop ID or coordinates)
- **Line filtering**: Monitor specific lines by filtering with comma-separated line numbers, per sensor
- **Destination filtering**: Filter by (substring) text match of destination(s) at a stop (useful for busy stops), per sensor
- **Configurable time window**: Set how many minutes ahead to search (1-1440 minutes), per sensor
- **Multiple transport modes**: Support for buses, trains, metro, trams, and ships
- **Flexible sensor configuration**: Create separate sensors for departures and arrivals
- **Stop lookup service**: Search for the stop ID by it's name using Home Assistant service
- **Config flow**: Easy setup through the Home Assistant UI with step-by-step configuration
- **Multi-language support**: English and Swedish translations
- **Nationwide coverage**: Covers all public transport operators in Sweden that are a part of Trafiklab API. 

The integration uses the newer **Trafiklab Realtime APIs**, which currently is in a beta release. Until the API is production-ready this integration will remain in "testing" state. See [Trafiklab Realtime API webpage](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/) for more information.


## Installation

### HACS (Recommended)

1. Search for "Trafiklab" in HACS
2. Install the integration
3. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/trafiklab` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

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
     - Time window and refresh interval
     - Optional Update Condition (template)
   - Travel Search:
     - Origin and Destination: each can be a Stop ID or coordinates "lat,lon" (select type for each)
     - Optional via/avoid Stop IDs and maximum walking distance
     - Time window and refresh interval
5. Finish to create the sensor.

**Note**: The integration now uses **area IDs** from the Trafiklab Realtime API, which correspond to "rikshållplatser" (national stops) or meta-stops. Use the stop lookup service to find the correct area ID for your stop.

#### Refresh interval considerations
The refresh interval controls how often the integration fetches data from the Trafiklab API. Consider your API quota limits when setting this value. More frequent updates (lower values) consume more API calls. For example, if you have a departure sensor for a stop that updates every 5 minutes (300 seconds), that sensor alone will consume about 8.640 calls per month. Thus, you can have up to 11 departure or arrival sensors with 300 seconds update frequency to stay within the maximum initial quota. 

## Sensors

The integration creates sensors based on your configuration:

### Departure Sensors (when sensor type is "Departures")
- **Next Departure Sensor** (`sensor.[name]_next_departure`)
  - **State**: Minutes until next departure (integer)
  - **Unit**: Minutes
  - **Device Class**: Duration
  - **Attributes**: Detailed information about the next departure

### Arrival Sensors (when sensor type is "Arrivals")
- **Next Arrival Sensor** (`sensor.[name]_next_arrival`)
  - **State**: Minutes until next arrival (integer)
  - **Unit**: Minutes
  - **Device Class**: Duration
  - **Attributes**: Detailed information about the next arrival

### Resrobot Travel Search Sensors (new)
- **Travel Search Sensor** (`sensor.[name]_resrobot_travel`)
  - **State**: Minutes until the first upcoming leg within the configured time window
  - **Unit**: Minutes
  - **Device Class**: Duration
  - **Attributes**: Normalized list of trips and legs (origin/destination times, product, category, duration, etc.)


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

### Automation Examples

#### Basic Departure Notification
```yaml
automation:
  - alias: "Bus departure notification"
    trigger:
      - platform: numeric_state
        entity_id: sensor.my_stop_next_departure
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
        entity_id: sensor.my_stop_next_departure
    condition:
      - condition: numeric_state
        entity_id: sensor.my_stop_next_departure
        below: 11
        above: 0
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "Next departure in {{ states('sensor.my_stop_next_departure') }} minutes"
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
          {{ state_attr('sensor.my_stop_next_departure', 'upcoming') 
             | selectattr('line', 'eq', '7') 
             | selectattr('minutes_until', '<=', 15) 
             | list | count > 0 }}
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Line 7 departures in next 15 minutes:
            {% set line7_departures = state_attr('sensor.my_stop_next_departure', 'upcoming') 
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
        entity_id: sensor.my_stop_next_departure
        attribute: upcoming
    condition:
      # Check if any upcoming departure is delayed more than 5 minutes
      - condition: template
        value_template: >
          {{ state_attr('sensor.my_stop_next_departure', 'upcoming') 
             | selectattr('delay_minutes', '>', 5) 
             | list | count > 0 }}
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Delayed departures detected:
            {% set delayed = state_attr('sensor.my_stop_next_departure', 'upcoming') 
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
        entity_id: sensor.my_stop_next_departure
        below: 3
    condition:
      - condition: template
        value_template: "{{ state_attr('sensor.my_stop_next_departure', 'platform') != '' }}"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Next departure from platform {{ state_attr('sensor.my_stop_next_departure', 'platform') }} 
            in {{ states('sensor.my_stop_next_departure') }} minutes!
```

### Stop ID Lookup Service

There are basically two ways of lookup the Stop ID. You can go directly to [Trafiklab API](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/openapi-specification/) where you can use the function to try out the Stop lookup API. Enter your API key and search string to get a response back.

The other way is to use the integration provided service to search for stops by name. Please note that the service only registers in Home Assistant if either:
1. You have at least one Trafiklab config entry; OR
2. You add an (optional) empty YAML stub in configuration.yaml:

```yaml
trafiklab:
```

When you have entered the YAML stub and restarted Home Assistant, you can now call the service:

```yaml
service: trafiklab.stop_lookup
data:
  api_key: "your_api_key"
  search_query: "Stockholm"
```

#### Service Response

The service returns data directly in the Services panel:
```yaml
search_query: "Stockholm"
total_stops: 3
stops_found:
  - id: "740098000" # <-- This is what you'll use as Stop ID when setting up a departure or arrival sensor
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

Events are not currently emitted; use the direct service response.

### Automation with Stop Lookup

```yaml
automation:
  - alias: "Find stops and notify"
    trigger:
      - platform: event
        event_type: trafiklab_stop_lookup_result
    action:
      - service: notify.persistent_notification
        data:
          message: >
            Found {{ event.data.stops_found | length }} stops for "{{ event.data.search_query }}":
            {% for stop in event.data.stops_found[:5] %}
            - {{ stop.name }} (ID: {{ stop.id }})
            {% endfor %}
```

### Lovelace Card Examples

#### Basic Entity Card
```yaml
type: entities
title: Bus Departures
entities:
  - entity: sensor.my_stop_next_departure
    name: Next Departure
    secondary_info: >
      Line {{ state_attr('sensor.my_stop_next_departure', 'line') }} 
      to {{ state_attr('sensor.my_stop_next_departure', 'destination') }}
show_header_toggle: false
```

#### Custom Card with Upcoming Departures
```yaml
type: markdown
title: Upcoming Departures
content: |
  **Next Departure:** {{ states('sensor.my_stop_next_departure') }} minutes
  
  **Upcoming:**
  {% for departure in state_attr('sensor.my_stop_next_departure', 'upcoming')[:5] %}
  - Line **{{ departure.line }}** to {{ departure.destination }} 
    at {{ departure.time_formatted }} ({{ departure.minutes_until }} min)
    {% if departure.delay_minutes > 0 %}⚠️ {{ departure.delay_minutes }}min delayed{% endif %}
  {% endfor %}
```

#### Gauge Card for Minutes Until Departure
```yaml
type: gauge
entity: sensor.my_stop_next_departure
name: Minutes Until Departure
min: 0
max: 30
severity:
  green: 10
  yellow: 5
  red: 0
```

## Operators

At the time of the initial release, the following operators are represented in the API

### Static (timetable) data and realtime traffic data

- SL (Stockholm)
- UL (Uppsala)
- Östgötatrafiken
- JLT (Jönköping)
- Kronoberg
- KLT (Kalmar)
- Skånetrafiken
- Värmlandstrafik
- Örebro, Länstrafiken
- Västmanland
- Dalatrafik
- X-trafik
- Din Tur (Västernorrland)

### Static (timetable) data

- Sörmlandstrafiken
- Gotland
- Blekingetrafiken
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
- Lennakatten
- Luleå Lokaltrafik
- Masexpressen
- Mälartåg
- Norrtåg
- Ressel Rederi
- Roslagens sjötrafik
- SJ
- SJ Norge
- Sjöstadstrafiken (Stockholm Stad)
- Skellefteåbuss
- Snälltåget
- Strömma Turism & Sjöfart AB
- TiB ersättningstrafik (VR Sverige)
- TJF Smalspåret
- Trosabussen
- Tågab
- VR
- Vy Tåg AB
- Vy Värmlandstrafik
- Vygruppen Norge
- Y-Buss

For current list of operators, please visit [Trafiklab Timetables page](https://www.trafiklab.se/sv/api/our-apis/trafiklab-realtime-apis/timetables/)

## API Documentation

This integration uses the following Trafiklab APIs and endpoints:

- [Trafiklab Realtime APIs](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/)
- [Trafiklab Timetables](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/timetables/) (for departures and arrivals)
- [Trafiklab Stop Lookup](https://www.trafiklab.se/api/our-apis/trafiklab-realtime-apis/stop-lookup/) (for finding stops)
- [Resrobot Travel Search](https://www.trafiklab.se/api/our-apis/resrobot-v21/) (via Trafiklab) for trip planning between origin and destination (separate API key)


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
- Claude Sonnet 4, for help sort things out whenever I'm a little out on the deep waters... Like I said - developing isn't my day job
