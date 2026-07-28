# BEAMS Light

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![Release](https://img.shields.io/github/v/release/realdigger/home-assistant-beams.svg)](https://github.com/realdigger/home-assistant-beams/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Unofficial Home Assistant custom integration for BEAMS reef aquarium lights.

This project is not affiliated with, endorsed by, or supported by BeautifulReef or BEAMS.

Русская версия: [README.ru.md](README.ru.md)

## Features

- Read-only main-light indicator
- Auto/manual mode and service-mode switches
- Overall brightness and 10 spectral channel controls
- Spectrum selector and refresh button for the controller gallery
- Configurable idle polling interval, with fast polling after a user action
- Configurable manual-mode duration from one to six hours and a remaining-time sensor
- Current daily-cycle DLI sensor
- Current PPFD sensors for `@25 cm`, `@35 cm`, and `@45 cm`
- Estimated power, light model, uptime, cycle timepoint, and light-uniformity sensors
- Controller ID, assembly count, and TrueSpectrum, OS, kernel, and LCS diagnostic versions
- Built-in Lovelace cards for colour-coded channel sliders and the current spectral distribution
- Services for setting channels, switching mode, applying spectra, and refreshing the spectrum gallery

## Supported devices

Tested with:

- BEAMS 2 PRO R-8

Other BEAMS lights may work if they expose the same local controller API.

## Installation

### HACS

1. Open HACS.
2. Go to **Integrations**.
3. Add custom repository:
   - Repository: `https://github.com/realdigger/home-assistant-beams`
   - Category: `Integration`
4. Install **BEAMS Light**.
5. Restart Home Assistant, then refresh the browser page once.

### Manual

Copy the integration folder to Home Assistant:

```text
/config/custom_components/beams_light/
```

Then restart Home Assistant.

## Configuration

Add the integration from:

```text
Settings → Devices & services → Add integration → BEAMS LED Light
```

Controller URL examples:

```text
http://beams2.sensors.local
http://10.11.1.1
http://192.168.1.55
```

No YAML configuration is required.

### Polling interval

Open the integration's **Configure** page to set the idle polling interval (5 to 3600 seconds; 10 seconds by default). After a user action, the controller is polled every 3 seconds for one minute before returning to the configured interval.

## Entities

### Main light indicator

```text
binary_sensor.<device_id>_light
```

Reports whether at least one light channel is active. It is an indicator only and cannot change the controller state.

### Mode and spectrum

```text
switch.<device_id>_manual_mode
switch.<device_id>_service_mode
select.<device_id>_spectrum
select.<device_id>_manual_duration
```

Turn on `switch.<device_id>_manual_mode` for manual control. Turn it off for automatic daily-cycle control.

In auto mode, the controls display the current levels but reject changes. The spectrum selector displays `Авто: дневной цикл`; the controller interpolates between daily-cycle points, so it does not have a single fixed spectrum name. Service mode sets every channel to 20%; switching it off returns the controller to auto mode.

The spectrum selector applies saved spectra from the controller gallery.

### Brightness and channels

```text
number.<device_id>_brightness
number.<device_id>_ch1_<led_type>
...
number.<device_id>_ch10_<led_type>
```

Values are shown as `0–100%` in Home Assistant. Changing the overall brightness preserves the relative channel levels. To change values, enable manual mode first.

Entity IDs include the configured device ID and the LED type returned by the controller. Use the entity IDs created for your device in Home Assistant.

Each channel exposes a `color` attribute from `/api/kit`, which can be used by custom Lovelace cards.

### Sensors

```text
sensor.<device_id>_current_cycle_dli
sensor.<device_id>_ppfd_25_cm
sensor.<device_id>_ppfd_35_cm
sensor.<device_id>_ppfd_45_cm
sensor.<device_id>_estimated_power
sensor.<device_id>_light_model
sensor.<device_id>_uptime
sensor.<device_id>_cycle_timepoint
sensor.<device_id>_light_uniformity
sensor.<device_id>_assembly_count
sensor.<device_id>_controller_id
sensor.<device_id>_kernel
sensor.<device_id>_lcs
sensor.<device_id>_operating_system
sensor.<device_id>_user_interface
sensor.<device_id>_manual_mode_remaining
```

`uptime` is displayed as days, hours, and minutes. `cycle_timepoint` is displayed as hours and minutes.

DLI is calculated from the current daily cycle data exposed by the controller. PPFD uses native coefficients when available and falls back to controller kit PPFD data.

The device page includes the model ID and number of assemblies. The controller ID is available as a diagnostic sensor. Version sensors are labelled **Kernel version**, **LCS version**, **OS version**, and **TrueSpectrum version**.

## Lovelace cards

The integration automatically registers two custom cards. After installing or updating the integration, refresh the Home Assistant browser page once so the frontend loads the card module.

### Colour-coded channels

```yaml
type: custom:beams-channel-card
title: BEAMS Channels
entities:
  - number.<device_id>_ch1_<led_type>
  - number.<device_id>_ch2_<led_type>
  # Add the remaining channel entities here.
```

The sliders use the colour reported by the controller. In auto mode they show current values, but changes are rejected by the integration.

### Current spectrum

```yaml
type: custom:beams-spectrum-card
title: Current spectrum
entity: binary_sensor.<device_id>_light
```

The card reproduces the TrueSpectrum calculation using the current channel levels and LED spectral curves returned by `GET /api/led`.

## Services

### Set channels

```yaml
service: beams_light.set_channels
data:
  channels: [20, 20, 20, 20, 20, 20, 20, 20, 20, 20]
```

Values are percentages. The controller is switched to manual mode.

### Set mode

```yaml
service: beams_light.set_mode
data:
  mode: manual
```

or:

```yaml
service: beams_light.set_mode
data:
  mode: auto
```

### Apply spectrum

```yaml
service: beams_light.apply_spectrum
data:
  spectrum: "Ice and fire #5"
```

or by numeric ID:

```yaml
service: beams_light.apply_spectrum
data:
  spectrum: 5
```

### Refresh spectrum gallery

```yaml
service: beams_light.refresh_spectrums
```

## Troubleshooting

Enable debug logging:

```yaml
logger:
  default: warning
  logs:
    custom_components.beams_light: debug
```

Check controller availability:

```bash
curl -v http://beams2.sensors.local/api/channels/get
```

If DLI or PPFD sensors are unavailable, check that the controller returns data from:

```text
/api/state/full
/api/kit
/api/math/get
/api/led
```

## License

MIT License. See [LICENSE](LICENSE).
