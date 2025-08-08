# Home Assistant Trafiklab Integration

[![Testing](https://img.shields.io/badge/project%20state-testing-yellow.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration)
[![Maintained](https://img.shields.io/badge/maintained-yes-brightgreen.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1.0+-blue.svg)](https://github.com/home-assistant/core/releases)
[![Integration Version](https://img.shields.io/badge/version-0.4.0-orange.svg)](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/releases)
[![HACS](https://img.shields.io/badge/HACS-custom-orange.svg)](https://github.com/hacs/integration)
[![Maintainer](https://img.shields.io/badge/maintainer-MrSjodin-blue.svg)](https://github.com/MrSjodin)
[![License](https://img.shields.io/badge/license-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

So, I have created a pretty simple (but hopefully quite usable) Home Assistant custom integration for Swedish public transport information by using the newer **Trafiklab Realtime API**.

The story behind is that I'd like to be able to show the upcoming departures from our nearest stops in the Home Assistant ecosystem, a bit outside of the city (and not in the SL area). Although HASL is a great integration, the newer versions only supports SL - therefore I saw a need to have a native integration towards the **Trafiklab Realtime API** for use in more or less the whole country.

For a complete list of traffic operators covered by the API and this integration, see **Operators** section below. 

## Integration Features

- **Real-time departures and arrivals**: Get live realtime departure and arrival information from any Trafiklab covered stop in Sweden
- **Line filtering**: Monitor specific lines by filtering with comma-separated line numbers, per sensor
- **Direction filtering**: Filter by specific directions at a stop (useful for busy stops), per sensor
- **Configurable time window**: Set how many minutes ahead to search (1-1440 minutes), per sensor
- **Multiple transport modes**: Support for buses, trains, metro, trams, and ships
- **Flexible sensor configuration**: Create separate sensors for departures and arrivals
- **Stop lookup service**: Search for the stop ID by it's name using Home Assistant service
- **Config flow**: Easy setup through the Home Assistant UI with step-by-step configuration
- **Multi-language support**: English and Swedish translations
- **Nationwide coverage**: Covers all public transport operators in Sweden that are a part of Trafiklab API. 

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Search for "Trafiklab" in HACS
3. Install the integration
4. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/trafiklab` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

## Configuration

### Prerequisites

1. Get a free API key from [Trafiklab](https://www.trafiklab.se/) - it's free but please note that there are a default API quota with the limitation of 25 calls per minute and 100.000 calls per month.
2. Find the area/stop ID for your desired stop using the Stop Lookup service (see below)

### Setup

1. Go to Settings → Devices & Services
2. Click "Add Integration"
3. Search for "Trafiklab"
4. Enter your API key and area/stop ID (see instructions below on how to use the Stop Lookup service)
5. Configure the integration name
6. Choose sensor type (departures or arrivals)
7. Optionally filter by specific lines (comma-separated, e.g., "1,4,7")
8. Optionally filter by direction (0 for direction 1, 1 for direction 2, leave empty for both)
9. Set time window (how many minutes ahead to search, default 60 minutes)
10. Configure refresh interval (how often to fetch data from API, default 300 seconds, minimum 60 seconds)

**Note**: The integration now uses **area IDs** from the Trafiklab Realtime API, which correspond to rikshållplatser (national stops) or meta-stops. Use the stop lookup service to find the correct area ID for your stop.

**Important**: The refresh interval controls how often the integration fetches data from the Trafiklab API. Consider your API quota limits when setting this value. More frequent updates (lower values) consume more API calls.

## API Keys

You need to register at [Trafiklab](https://www.trafiklab.se/) to get API keys for:

- **Trafiklab Realtime APIs**: For real-time departures, arrivals, and stop lookup

The integration uses the new **Trafiklab Realtime APIs** which provide:
- Better performance with higher quotas
- More detailed data including platforms and real-time information
- Nationwide coverage of all Swedish public transport operators - not just SL
- CC-BY 4.0 license allowing flexible usage

## Sensors

The integration creates sensors based on your configuration:

### Departure Sensors (when sensor type is "Departures")
- **Next Departure Sensor** (`sensor.[name]_next_departure`)
  - **State**: Display time of the next departure
  - **Attributes**: Line, destination, route_direction, expected time, real-time status, transport mode, deviations, scheduled_time

- **Departures Sensor** (`sensor.[name]_departures`) 
  - **State**: Number of upcoming departures
  - **Attributes**: Array of upcoming departures with detailed information (upcoming_departures)

### Arrival Sensors (when sensor type is "Arrivals")
- **Next Arrival Sensor** (`sensor.[name]_next_arrival`)
  - **State**: Display time of the next arrival
  - **Attributes**: Line, destination, route_direction, expected time, real-time status, transport mode, deviations, scheduled_time

- **Arrivals Sensor** (`sensor.[name]_arrivals`)
  - **State**: Number of upcoming arrivals  
  - **Attributes**: Array of upcoming arrivals with detailed information (upcoming_arrivals)

### Common Attributes
All sensors include these additional attributes:
- `sensor_type`: Whether this tracks "departure" or "arrival"
- `line_filter`: Configured line filter (if any)
- `direction`: Configured direction filter (0=Direction 1, 1=Direction 2, 2=Both directions)  
- `time_window`: Configured time window in minutes
- `refresh_interval`: How often data is refreshed in seconds
- `last_updated`: Timestamp of last successful data update

### Upcoming Departures/Arrivals Array Structure
Each item in the `upcoming_departures` or `upcoming_arrivals` array contains:
- `line`: Bus/train line number
- `destination`: Final destination name
- `route_direction`: API direction value for this specific departure/arrival
- `time`: Display time (formatted for readability)
- `scheduled_time`: Original scheduled time
- `expected_time`: Real-time expected time
- `transport_mode`: Type of transport (bus, metro, train, etc.)
- `real_time`: Boolean indicating if real-time data is available
- `deviations`: Array of alerts/disruptions for this departure/arrival

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

**Direction Filter Explanation:**
- Configuration "Direction 1" → Sensor shows `direction: "0"`
- Configuration "Direction 2" → Sensor shows `direction: "1"`  
- Configuration "Both directions" → Sensor shows `direction: "2"`

### Automation Examples

#### Basic Departure Notification
```yaml
automation:
  - alias: "Bus departure notification"
    trigger:
      - platform: state
        entity_id: sensor.my_stop_next_departure
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state == '5 min' }}"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: "Bus {{ state_attr('sensor.my_stop_next_departure', 'line') }} to {{ state_attr('sensor.my_stop_next_departure', 'destination') }} departing in 5 minutes!"
```

#### Working with Upcoming Departures Array
```yaml
automation:
  - alias: "Next 3 departures notification"
    trigger:
      - platform: time_pattern
        minutes: "/5"  # Every 5 minutes
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Next departures:
            {% for departure in state_attr('sensor.my_stop_departures', 'upcoming_departures')[:3] %}
            Line {{ departure.line }} to {{ departure.destination }} at {{ departure.time }}
            {% endfor %}
```

### Stop Lookup Service

The integration provides a service to search for stops by name:

```yaml
service: trafiklab.stop_lookup
data:
  api_key: "your_api_key"
  search_query: "Stockholm"
```

#### Service Response

The service returns data directly in the Services page and also fires events for automation use:

**Direct Response (visible on Services page):**
```yaml
search_query: "Stockholm"
total_stops: 3
stops_found:
  - id: "740098000"
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

**Events (for automations):**
This service will fire an event `trafiklab_stop_lookup_result` with the search results, or `trafiklab_stop_lookup_error` if there's an error.

#### Service Response Event Data

```yaml
event_type: trafiklab_stop_lookup_result
event_data:
  search_query: "Stockholm"
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
        # ... more child stops
```

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

### Lovelace Card Example

```yaml
type: entities
title: Bus Departures
entities:
  - entity: sensor.my_stop_next_departure
    name: Next Departure
  - entity: sensor.my_stop_departures
    name: Total Departures
show_header_toggle: false
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


## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License - see the [LICENSE](LICENSE) file for details.

## Support

- [Report Issues](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues)
- [Trafiklab API Documentation](https://www.trafiklab.se/api/)
- [Home Assistant Developer Docs](https://developers.home-assistant.io/)

## Updates, todo's/roadmap, issues and feature requests

Developing isn't my day job - I'm taking care of this integration solely on my free time. This means that I most probably won't try the integration out in pre-releases of Home Assistant updates. Thus, it might break in the .0 versions of Home Assistant releases before I'm able to take care of it. Feel free to contribute though!

- Todo: Add support for the Trafiklab Route Planner
- Todo: Add functionality to only update integration sensors if "something" is true, by using a template sensor for example
- [Feature Request (mark as "FR")](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues)
- [Report Issues](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Integration/issues)
- [Trafiklab API Documentation](https://www.trafiklab.se/api/)

## Acknowledgments

- [Trafiklab](https://www.trafiklab.se/) for providing the excellent public transport API
- Home Assistant community for excellent development documentation
- [HASL developers](https://github.com/hasl-sensor/) for the integration that basically provided the idea behind this integration
- Claude Sonnet 4, for help sort things out whenever I'm a little out on the deep waters... Like I said - developing isn't my day job