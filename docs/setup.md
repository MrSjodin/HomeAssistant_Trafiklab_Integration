# Trafiklab Home Assistant Integration — Installation & Configuration Guide

[← Back to the main README](../README.md)

Full walkthrough for finding your Trafiklab Stop ID, setting up a sensor, configuration examples, and the available filters and templates for departure, arrival, and travel search sensors.

## Finding Your Stop ID

A **Stop ID** is required for **Realtime departure and arrival sensors**, and it is also one supported way to configure **Travel Search** sensors. Travel Search sensors and the `trafiklab.travel_search` service can also use coordinates, stop names, HA zones, or person/device_tracker entities. If you want to use a Stop ID, use the built-in `trafiklab.stop_lookup` service — see [Stop ID Lookup Service](reference.md#stop-id-lookup-service) for full details.

Please note that the Trafiklab Stop ID's are **not** the same as SL stop/station ID.

### Method 1 — Search the stop directly through a web request
This is probably the easiest way to search for your first stop ID - although the web response may be a little difficult to read out... You need a Realtime

1. Browse to https://realtime-api.trafiklab.se/v1/stops/name/{the-stop-to-search-for}?key={your-realtime-api-key}
2. For example - if you'd like to search for "Medborgarplatsen" and your API key is "abcdefghijk1234567890" you'd use https://realtime-api.trafiklab.se/v1/stops/name/Medborgarplatsen?key=abcdefghijk1234567890
3. You'll get a JSON response back, what you need to look for is the stop you wanted (as `name`) where the Stop ID is just before that (as `id`) - usually starts with `7`.

### Method 2 — Add a `trafiklab:` stub config to your `configuration.yaml`
If you have no Trafiklab config entries set up yet, the stop lookup service won't be there (classic catch 22). If you still like to use the Stop ID lookup service, you need to activate the integration manually...

1. Add this one-line stub to `configuration.yaml`:
   ```yaml
   trafiklab:
   ```
2. Restart Home Assistant
3. Open **Developer Tools → Services**, select `trafiklab.stop_lookup`
4. Enter your **Realtime API key** and a search string (your stop or town name)
5. Copy the `id` value from the response — that is your **Stop ID**
6. **After** you have configured your first sensor it's safe to remove the stub from `configuration.yaml`

## Setting Up a Sensor

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
     - Optional maximum number of results (default 10)
   - Travel Search:
     - Origin and Destination: each can be a Stop ID or coordinates "lat,lon" (select type for each)
     - Optional via/avoid Stop IDs and maximum walking distance
     - Optional transport mode filter (Bus, Metro, Train, Tram, Boat/Ferry — leave empty for all)
     - Time window and refresh interval
     - Optional maximum trip duration (in minutes) — trips longer than this are excluded from results
     - Optional maximum number of results (default 10)
5. Finish to create the sensor.

**Note**: The integration now uses **area IDs** from the Trafiklab Realtime API, which correspond to "rikshållplatser" (national stops) or meta-stops. Use the stop lookup service to find the correct area ID for your stop.

### Refresh interval considerations
The refresh interval controls how often the integration fetches data from the Trafiklab API. Consider your API quota limits when setting this value. More frequent updates (lower values) consume more API calls. For example, if you have a departure sensor for a stop that updates every 5 minutes (300 seconds), that sensor alone will consume about 8.640 calls per month. Thus, you can have up to 11 departure or arrival sensors with 300 seconds update frequency to stay within the maximum initial quota.

## Configuration Examples

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

## Filters

### Destination Filter
You can enter any (part of) destination text (case-insensitive). Example: entering `central` will match destinations like "Stockholm Central" or "Centralstationen". Leave empty for all destinations.

### Transport Mode Filter
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

## Update Condition (Template)
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

## Sensor State Format
- Sensor state returns **integer minutes** until next departure/arrival
- Positive numbers indicate future departures (e.g., `15` = 15 minutes until departure)
- Zero indicates departure happening now
- Negative numbers indicate past departures (useful for detecting delays)
- `null`/`unavailable` indicates no data available
