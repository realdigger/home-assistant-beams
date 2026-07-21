"""Regression tests for controller-derived DLI and PPFD values."""
from __future__ import annotations

from pytest import approx

from custom_components.beams_light.api import as_bool
from custom_components.beams_light.coordinator import BeamsCoordinator


KIT_CHANNEL_PPFDS = [
    83.66665,
    72.91685,
    114.4169,
    112.85,
    97.7163,
    49.0164,
    38.8672,
    63.50055,
    52.7338,
    72.78345,
]

CYCLE_POINTS = [
    (3600, [0.0] * 10),
    (36000, [0.0] * 10),
    (44327, [0.2111, 0.3941, 0.3941, 0.4083, 0.1826, 0.084, 0.0274, 0.0356, 0.0274, 0.0374]),
    (54218, [0.0288, 0.1189, 0.1273, 0.3256, 0.3572, 0.2046, 0.2014, 0.4157, 0.3403, 0.0003]),
    (64800, [0.1311, 0.5265, 0.5265, 0.5197, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    (86100, [0.0971, 0.489, 0.489, 0.489, 0.1461, 0.0, 0.0, 0.0, 0.0, 0.0]),
]


def _coordinator() -> BeamsCoordinator:
    coordinator = object.__new__(BeamsCoordinator)
    coordinator.data = {
        "channels": [0.0] * 10,
        "full": {
            "dailyCycle": {
                "spectrums": [
                    {"time": time, "channels": channels} for time, channels in CYCLE_POINTS
                ]
            }
        },
        "kit": {
            "channels": [
                {"totalPPFD": value, "color": "#0044FF" if index == 3 else "#000000"}
                for index, value in enumerate(KIT_CHANNEL_PPFDS)
            ],
            "specification": {"assembly_count": 8},
        },
        "ui": {
            "software": {
                "kernel": "6.1.82",
                "lcs": {"version": "560", "hash": "f3bcc6b8"},
                "os": {"version": "60196", "hash": "b60aa0bd"},
                "scripts": {"version": "200", "hash": "fa26a2e2"},
                "ui": {"version": "1717", "hash": "9aff5c12"},
            },
            "questForm": {
                "isComplete": True,
                "aquriumType": "salty",
                "length": "100",
                "width": "40",
                "ledCounts": {"BEAMS PRO-R-8": "1"},
            }
        },
        "math": {"led_correction": {"value": 1.0}},
    }
    return coordinator


def test_daily_cycle_dli_matches_controller_ui() -> None:
    """The controller schedule from BEAMS 2 PRO R-8 produces UI DLI 9.5."""
    coordinator = _coordinator()

    assert coordinator.current_cycle_dli == approx(9.4965, abs=0.0001)


def test_daily_cycle_dli_matches_native_ui_over_api_value() -> None:
    """Prefer the native UI calculation when firmware exposes a different DLI."""
    coordinator = _coordinator()
    coordinator.data["full"]["dailyCycle"]["dli"] = 8.3163525253282

    assert coordinator.current_cycle_dli == approx(9.4965, abs=0.0001)
    assert coordinator.current_cycle_dli_source == (
        "calculated: dailyCycle.spectrums + kit.channels.totalPPFD + math.led_correction"
    )


def test_as_bool_handles_string_values() -> None:
    """Firmware string flags must not treat 'false' as enabled."""
    assert as_bool("true") is True
    assert as_bool("false") is False


def test_ppfd_25cm_uses_native_kit_coefficients() -> None:
    """PPFD uses native kit coefficients and remains zero while all channels are off."""
    coordinator = _coordinator()

    assert coordinator.ppfd_25cm == 0.0
    coordinator.data["channels"] = CYCLE_POINTS[2][1]
    assert coordinator.ppfd_25cm == 190.4


def test_ppfd_35cm_and_45cm_match_native_ui_geometry_model() -> None:
    """PPFD @35/@45cm uses the controller UI aquarium geometry fallback."""
    coordinator = _coordinator()
    coordinator.data["channels"] = CYCLE_POINTS[2][1]

    assert coordinator.ppfd_35cm == 128.52
    assert coordinator.ppfd_45cm == 109.67


def test_light_uniformity_matches_native_ui() -> None:
    """The native @25cm UI model reports the configured aquarium as acceptable."""
    assert _coordinator().light_uniformity == "acceptable"


def test_diagnostic_versions_are_read_from_ui_payload() -> None:
    """Software diagnostics use the controller UI payload without extra API calls."""
    coordinator = _coordinator()

    assert coordinator.assembly_count == 8
    assert coordinator.software_version("kernel") == "6.1.82"
    assert coordinator.software_version("lcs") == "560"
    assert coordinator.software_hash("lcs") == "f3bcc6b8"


def test_controller_id_uses_device_identifier() -> None:
    """The controller API identifier is exposed separately from the serial number."""
    coordinator = _coordinator()
    coordinator.data["device_info"] = {"ident": "110795"}

    assert coordinator.controller_id == "110795"


def test_channel_color_comes_from_controller_kit() -> None:
    """Channel colors are exposed by the controller rather than hardcoded."""
    assert _coordinator().channel_color(3) == "#0044FF"
