# BEAMS Light

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Unofficial Home Assistant custom integration for BEAMS reef aquarium lights.

This project is not affiliated with, endorsed by, or supported by BeautifulReef or BEAMS.

## Features

- Main light entity with on/off and brightness-style control
- Auto/manual mode selector
- 10 spectral channel controls
- Spectrum selector from the controller gallery
- Current daily-cycle DLI sensor
- Current PPFD sensors for `@25 cm`, `@35 cm`, and `@45 cm`
- Estimated power, light model, uptime, and cycle timepoint sensors
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
   - Repository: `https://github.com/realdigger/home-assistant-beams-light`
   - Category: `Integration`
4. Install **BEAMS Light**.
5. Restart Home Assistant.

### Manual

Copy the integration folder to Home Assistant:

```text
/config/custom_components/beams_light/
```

Then restart Home Assistant.

## Configuration

Add the integration from:

```text
Settings → Devices & services → Add integration → BEAMS Light
```

Controller URL examples:

```text
http://beams2.sensors.local
http://10.11.1.1
http://192.168.1.55
```

No YAML configuration is required.

## Entities

### Light

```text
light.beams_light
```

Basic light control. For accurate spectral control, use the channel entities.

### Selects

```text
select.beams_light_mode
select.beams_light_spectrum
```

Modes:

```text
auto
manual
```

The spectrum selector applies saved spectra from the controller gallery.

### Channels

```text
number.beams_light_ch1_dark_violet_410_420_nm
number.beams_light_ch2_violet_420_430_nm
number.beams_light_ch3_indigo_440_445_nm
number.beams_light_ch4_blue_455_460_nm
number.beams_light_ch5_sky_blue_475_480_nm
number.beams_light_ch6_turquoise_496_500_nm
number.beams_light_ch7_green_525_530_nm
number.beams_light_ch8_mint_556_nm
number.beams_light_ch9_pc_amber_595_nm
number.beams_light_ch10_red_624_634_nm
```

Values are shown as `0–100%` in Home Assistant.

### Sensors

```text
sensor.beams_light_current_cycle_dli
sensor.beams_light_ppfd_25cm
sensor.beams_light_ppfd_35cm
sensor.beams_light_ppfd_45cm
sensor.beams_light_estimated_power
sensor.beams_light_light_model
sensor.beams_light_uptime
sensor.beams_light_cycle_timepoint
```

DLI is calculated from the current daily cycle data exposed by the controller.

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
```

## License

MIT License. See [LICENSE](LICENSE).
