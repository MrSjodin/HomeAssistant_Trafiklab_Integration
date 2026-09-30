# Home Assistant Trafiklab Integration

![Home Assistant Version](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fraw.githubusercontent.com%2FMrSjodin%2FHomeAssistant_Trafiklab_Integration%2Fmain%2Fhacs.json&query=%24.homeassistant&label=Home%20Assistant&color=blue)
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
- [Configuration](#configuration)
- [Sensors](#sensors)
- [Services](#services)
- [Dashboard & Lovelace Cards](#dashboard--lovelace-cards)
- [Automation Examples](#automation-examples)
- [Operators](#operators)
- [API Documentation](#api-documentation)

**In-depth guides:**
- [Installation & Configuration Guide](docs/setup.md) — Stop ID lookup, full setup walkthrough, configuration examples, filters and templates
- [Sensor & Service Reference](docs/reference.md) — attribute schemas and full service request/response examples
- [Automation & Dashboard Examples](docs/examples.md) — ready-to-use automations and Lovelace cards

---

## Features

- **Real-time departures and arrivals**: Live departure and arrival information from any Trafiklab-covered stop in Sweden
- **Resrobot end-to-end travel search**: Trip planning between origin and destination (stop ID, coordinates, stop name, HA zone, or person entity)
- **Line filtering**: Monitor specific lines by filtering with comma-separated line numbers, per sensor
- **Destination filtering**: Filter by (substring) text match of destination(s) at a stop (useful for busy stops), per sensor
- **Configurable time window**: Set how many minutes ahead to search (1-1440 minutes), per sensor
- **Configurable result count**: Set how many departures/arrivals or trips are returned (1-100, default 10), per sensor
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

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=MrSjodin&repository=HomeAssistant_Trafiklab_Integration&category=integration)

### Manual Installation

1. Copy the `custom_components/trafiklab` folder to your Home Assistant `custom_components` directory
2. Restart Home Assistant

### Prerequisites

1. Get your API key(s) from [Trafiklab](https://www.trafiklab.se/) - it's free but please note that there are a default API quota with API call limitation.
2. Find the area/stop ID for your desired stop using the Stop Lookup service — see [Finding Your Stop ID](docs/setup.md#finding-your-stop-id)
3. Use Home Assistant 2024.8.0 or newer

**Note about Resrobot:** Trip planning uses Resrobot Travel Search which requires its own API key, requested from the same Trafiklab website where you request the Realtime API key. Make sure to activate/request both keys if you plan to use both sensor types.

**Note about API cross-checking:** The Resrobot Travel Search sensor is able to cross-check for realtime data using the Realtime API if possible. Therefore I strongly recommend that you get API keys for both, and set up at least one Arrival/Departure sensor prior to configuring a Resrobot sensor (the Realtime API key is then looked up automatically by the Resrobot sensor).

📖 **Full guide:** Stop ID lookup methods, the config-flow setup walkthrough, refresh-interval/API-quota guidance — [docs/setup.md](docs/setup.md)

## Configuration

Configuration happens entirely through the Home Assistant UI: **Settings → Devices & Services → Add Integration → "Trafiklab"**. Pick a sensor type — Departures, Arrivals, or Travel Search — then supply:

- **Departures/Arrivals**: an Area/Stop ID, optional line/destination/transport-mode filters, time window, refresh interval, and an optional Update Condition template
- **Travel Search**: an origin and destination (Stop ID or coordinates), optional via/avoid stops, transport-mode filter, time window, and an optional maximum trip duration

The integration uses **area IDs** ("rikshållplatser"/meta-stops) from the Trafiklab Realtime API — use the Stop Lookup service to find yours.

📖 **Full guide:** step-by-step setup, all three configuration examples, and the Destination/Transport-mode/Update-Condition filter reference — [docs/setup.md](docs/setup.md)

## Sensors

The integration creates one sensor per configured entry (`sensor.trafiklab_departure_*`, `sensor.trafiklab_arrival_*`, or `sensor.trafiklab_travel_*`). State is the integer number of minutes until the next departure, arrival, or trip leg; rich details are exposed as attributes (`upcoming` for Departures/Arrivals, `trips` for Travel Search).

Travel Search sensors additionally support a **Maximum Trip Duration** filter, and both sensor families support a **Maximum Number of Results** setting and optional **Realtime Delay Cross-Check** against the Trafiklab Realtime API.

📖 **Full reference:** entity naming, per-type sensor details, and the complete `upcoming`/`trips` attribute JSON schemas — [docs/reference.md](docs/reference.md)

## Services

- **`trafiklab.travel_search`** — ad-hoc Resrobot journey search (stop ID, coordinates, name, zone, or person) without a permanent sensor
- **`trafiklab.update_now`** — force an immediate data refresh for one or all configured sensors
- **`trafiklab.stop_lookup`** — find a stop's national Stop ID by name
- **`trafiklab.trip_details`** — look up the full route/calls for one departure or arrival by `trip_id`

📖 **Full reference:** request/response examples and parameters for every service — [docs/reference.md#services](docs/reference.md#services)

## Dashboard & Lovelace Cards

There are companion dashboard cards designed for this integration:
- [Timetable card](https://github.com/MrSjodin/HomeAssistant_Trafiklab_Timetable_Card) — shows upcoming departures/arrivals in a timetable layout
- [Travel Search card](https://github.com/MrSjodin/HomeAssistant_Trafiklab_TravelSearch_Card) — shows journey results from a Travel Search sensor
- [Dynamic Travel Search card](https://github.com/MrSjodin/HomeAssistant_Trafiklab_DynamicTravelSearch_Card) — search ad-hoc for an end-to-end travel, to and from My Location, Stops, HA Zones and Persons

The sensors also work with any standard HA card (entities, markdown, gauge, etc.) — see [docs/examples.md](docs/examples.md) for ready-made snippets.

## Automation Examples

Trigger notifications on upcoming departures, delays, or platform changes using the `upcoming`/`trips` attributes in templates.

📖 **Full examples:** delay detection, line-specific filtering, and platform notifications — [docs/examples.md](docs/examples.md)

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
- Västmanland, Svealandstrafiken
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
- Lennakatten
- Luleå Lokaltrafik
- Masexpressen
- Mälartåg ersättningstrafik
- Nikkaluoktaexpressen
- Norrtåg ersättningsstrafik (VR Sverige)
- Ressel Rederi
- Silverlinjen
- SJ
- SJ Norge
- Sjöstadstrafiken (Stockholm Stad)
- Skellefteåbuss
- Snälltåget
- Stavsnäs båttaxi
- Strömma Turism & Sjöfart AB
- TiB ersättningstrafik (VR Sverige)
- TJF Smalspåret
- Trafikverket RDB
- Trosabussen
- Tågab
- Uddevalla Skärgårdsbåtar AB
- VR
- Vy Bus4You
- Vy Flygbussarna
- Vy Norge
- Vy Tåg AB
- Vy Värmlandstrafik
- Västervik Express
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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

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
