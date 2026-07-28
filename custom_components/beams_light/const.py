"""Constants for the BEAMS Light integration."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "beams_light"
DEFAULT_NAME = "BEAMS LED Light"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=3)
DEFAULT_IDLE_SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_TIMEOUT = 10

CONF_MANUAL_CHANNELS = "manual_channels"
CONF_BASE_URL = "base_url"
CONF_LAST_MODE = "last_mode"
CONF_LAST_SPECTRUM = "last_spectrum"
CONF_MANUAL_DURATION_HOURS = "manual_duration_hours"
CONF_MANUAL_SESSION_DEADLINE = "manual_session_deadline"
CONF_MANUAL_SESSION_RENEWED_AT = "manual_session_renewed_at"
CONF_MANUAL_SPECTRUM_MODE = "manual_spectrum_mode"
CONF_IDLE_SCAN_INTERVAL = "idle_scan_interval"

MODE_AUTO = "auto"
MODE_MANUAL = "manual"

SPECTRUM_OPTION_MANUAL = "Ручной"
SPECTRUM_OPTION_SERVICE = "Сервисный"

DEFAULT_CHANNEL_COUNT = 10
DEFAULT_MANUAL_VALUE = 0.20

ATTR_CHANNELS = "channels"
ATTR_CHANNELS_PERCENT = "channels_percent"
ATTR_MODE = "mode"
ATTR_ENTRY_ID = "entry_id"
ATTR_SPECTRUM = "spectrum"

SERVICE_SET_CHANNELS = "set_channels"
SERVICE_SET_MODE = "set_mode"
SERVICE_APPLY_SPECTRUM = "apply_spectrum"
SERVICE_REFRESH_SPECTRUMS = "refresh_spectrums"

CHANNEL_NAMES = [
    "Dark Violet 410-420 nm",
    "Violet 420-430 nm",
    "Indigo 440-445 nm",
    "Blue 455-460 nm",
    "Sky Blue 475-480 nm",
    "Turquoise 496-500 nm",
    "Green 525-530 nm",
    "Mint 556 nm",
    "PC Amber 595 nm",
    "Red 624-634 nm",
]
