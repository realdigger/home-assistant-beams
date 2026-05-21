# Changelog

## 0.7.7

- Current cycle DLI is now rounded to one decimal place.

## 0.7.6

- Changed `sensor.beams_light_uptime` display format to days, hours, and minutes, for example `2 д 5 ч 17 мин`.
- Changed `sensor.beams_light_cycle_timepoint` display format to hours and minutes, for example `12 ч 30 мин`.

## 0.7.5

- Added a README disclaimer that the project is not affiliated with, endorsed by, or supported by BeautifulReef or BEAMS.

## 0.7.4

- Removed the sentence about local HTTP API operation and cloud access from `README.md`.

## 0.7.3

- Shortened `README.md`: removed secondary details, the long internal API endpoint list, verbose limitations, and redundant explanations.
- Kept only the essential GitHub/HACS sections: description, installation, configuration, entities, services, troubleshooting, and license.

## 0.7.2

- Fixed current daily-cycle DLI: it is now calculated the same way as the native web UI, from `dailyCycle.spectrums`, `kit.channels[*].totalPPFD`, `math.led_correction.value`, and the aquarium setup correction when available.
- Added the `source` attribute to `sensor.beams_light_current_cycle_dli` to show where the DLI value came from.
- Kept the previous `dli` API-field lookup only as a fallback for firmware builds that expose a precomputed DLI value.

## 0.7.1

- Added a diagnostic light model sensor from the `kit_name` field returned by `GET /api/kit`: `sensor.beams_light_light_model`.
- Added a diagnostic controller uptime sensor: `sensor.beams_light_uptime`.
- Uptime extraction now checks common API fields such as `uptime`, `upTime`, `uptimeSeconds`, `uptimeMs`, `systemUptime`, `runtime`, `runTime`, `aliveTime`, and boot timestamps from `/info` when available.
- `/info` is now also read during regular updates so uptime can refresh without restarting Home Assistant.

## 0.7.0

- Renamed the package to `BEAMS Light`.
- Changed the integration domain to `beams_light`.
- Removed references to the previous controller branding from code, translations, README, changelog, and HACS metadata.
- Added MIT license file: `LICENSE`.

## 0.6.1

- Added `hacs.json` to the repository/package root for HACS custom repository installation.
- Updated `manifest.json` version to `0.6.1`.
- Added GitHub documentation and issue tracker links to `manifest.json`, and set code owner to `@realdigger`.
- Included the updated GitHub/HACS-ready `README.md`.

## 0.6.0

- Added separate current PPFD sensors for `@25cm`, `@35cm`, and `@45cm`:
  - `sensor.beams_light_ppfd_25cm`;
  - `sensor.beams_light_ppfd_35cm`;
  - `sensor.beams_light_ppfd_45cm`.
- PPFD is calculated from the current channel values and BEAMS coefficients from `/api/math/get` when available.
- Added an `@25cm` fallback based on the matched gallery spectrum `totalPPFD` when PPFD coefficients are unavailable.
- Added Russian and English translations for the new sensor names.

## 0.5.0

- Added explicit current daily-cycle DLI display: `sensor.beams_light_current_cycle_dli`.
- Improved DLI extraction: the integration now checks multiple BEAMS payload variants instead of only `full.dailyCycle.dli`.
- The DLI sensor is now explicitly named “Current cycle DLI”.

## 0.4.0

- Added spectrum gallery support through `GET /api/spectrums`.
- Added a spectrum selector entity: `select.*_spectrum`.
- Added the `beams_light.apply_spectrum` service to apply a spectrum by name, option label, or numeric ID.
- Added the `beams_light.refresh_spectrums` service to reload the gallery without restarting Home Assistant.
- Applying a spectrum writes its channel array to `POST /api/channels/set` and switches the controller to manual mode so the spectrum is applied immediately.
- Added current matched spectrum metadata to the main light entity attributes: name, ID, and `total_ppfd`.

## 0.3.0

- Fixed manual mode switching order to match the native web UI: first `POST /api/channels/set`, then `POST /api/state/set {"manual": true}`.
- Set update interval to 3 seconds.

## 0.2.0

- Read current channel values from `GET /api/channels/get`.
- Added DLI, estimated power, and cycle timepoint diagnostic sensors.

## 0.1.0

- Initial BEAMS custom integration.
