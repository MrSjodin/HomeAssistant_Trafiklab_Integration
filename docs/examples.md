# Trafiklab Home Assistant Integration — Automation & Dashboard Examples

[← Back to the main README](../README.md)

Copy-paste automation snippets and Lovelace card examples built around the Departure, Arrival, and Travel Search sensors.

## Automation Examples

### Basic Departure Notification
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

### Check for Departures Soon
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

### Working with Upcoming Array - Line-Specific Automation
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

### Delay Detection
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

### Platform-Specific Information
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

## Dashboard Card Examples

For purpose-built dashboard cards see the companion repos linked in the [main README](../README.md#dashboard--lovelace-cards). The sensors also work with any standard HA card — some examples:

### Basic Entity Card
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

### Custom Card with Upcoming Departures
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

### Gauge Card for Minutes Until Departure
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
