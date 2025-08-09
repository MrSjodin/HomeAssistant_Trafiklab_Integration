name: Report an issue with Trafiklab Integration
description: Report an issue with Trafiklab Integration.
body:
  - type: markdown
    attributes:
      value: |
        This issue form is for reporting bugs only!

  - type: textarea
    validations:
      required: true
    attributes:
      label: The problem
      description: >-
        Describe the issue you are experiencing here, to communicate to the
        maintainer(s). Tell us what you were trying to do and what happened.

        Provide a clear and concise description of what the problem is.
  - type: markdown
    attributes:
      value: |
        ## Environment
  - type: input
    id: version
    validations:
      required: true
    attributes:
      label: What version of Trafiklab Integration are you using?
      placeholder: integration-
      description: >
        Can be found in: [Settings ⇒ Integrations ⇒ Trafiklab](https://my.home-assistant.io/redirect/integration/?domain=trafiklab).

        [![Open your Home Assistant instance and show your integrations.](https://my.home-assistant.io/badges/integrations.svg)](https://my.home-assistant.io/redirect/integrations/)
  - type: input
    id: ha_version
    validations:
      required: true
    attributes:
      label: What version of Home Assistant are you using?
      placeholder: hass-
      description: >
        Can be found in: [Settings ⇒ System ⇒ Repairs ⇒ Three Dots in Upper Right ⇒ System information](https://my.home-assistant.io/redirect/system_health/).

        [![Open your Home Assistant instance and show the system information.](https://my.home-assistant.io/badges/system_health.svg)](https://my.home-assistant.io/redirect/system_health/)
  - type: markdown
    attributes:
      value: |
        # Details
  - type: textarea
    attributes:
      label: Diagnostics information
      placeholder: "drag-and-drop the diagnostics data file here (do not copy-and-paste the content)"
      description: >-
        You can [download diagnostic data](https://www.home-assistant.io/docs/configuration/troubleshooting/#debug-logs-and-diagnostics).

        **It would really help if you could download the diagnostics data for the integration,
        and <ins>drag-and-drop that file into the textbox below.</ins>**

        It generally allows pinpointing defects and thus resolving issues faster.
  - type: textarea
    attributes:
      label: Example YAML snippet
      description: |
        If applicable, please provide an example piece of YAML that can help reproduce this problem.
        This can be from an automation, script, scene or configuration.
      render: yaml
  - type: textarea
    attributes:
      label: Anything in the logs that might be useful?
      description: For example, error message, or stack traces.
      render: txt
  - type: textarea
    attributes:
      label: Additional information
      description: >
        If you have any additional information for us, use the field below.