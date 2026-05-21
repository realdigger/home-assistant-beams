"""Coordinator for BEAMS Light."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BeamsApiError, BeamsLightApi, as_float_channels
from .const import (
    CHANNEL_NAMES,
    CONF_LAST_MODE,
    CONF_LAST_SPECTRUM,
    CONF_MANUAL_CHANNELS,
    DEFAULT_CHANNEL_COUNT,
    DEFAULT_MANUAL_VALUE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODE_AUTO,
    MODE_MANUAL,
)

_LOGGER = logging.getLogger(__name__)

SPECTRUM_MATCH_TOLERANCE = 0.0006
SECONDS_PER_DAY = 86_400

# Same assembly-count map as used by the native controller UI when applying
# aquarium setup corrections to PPFD/DLI calculations.
BEAMS_ASSEMBLY_COUNTS: dict[str, int] = {
    "BEAMS-F-4": 4,
    "BEAMS-F-6": 6,
    "BEAMS-F-8": 8,
    "BEAMS-F-10": 10,
    "BEAMS-R-4": 4,
    "BEAMS-R-6": 6,
    "BEAMS-R-8": 8,
    "BEAMS-R-10": 10,
    "BEAMS PRO-F-4": 4,
    "BEAMS PRO-F-6": 6,
    "BEAMS PRO-F-8": 8,
    "BEAMS PRO-F-10": 10,
    "BEAMS PRO-R-4": 4,
    "BEAMS PRO-R-6": 6,
    "BEAMS PRO-R-8": 8,
    "BEAMS PRO-R-10": 10,
    "BEAMS PRO2-F-4": 4,
    "BEAMS PRO2-F-6": 6,
    "BEAMS PRO2-F-8": 8,
    "BEAMS PRO2-F-10": 10,
    "BEAMS PRO2-R-4": 4,
    "BEAMS PRO2-R-6": 6,
    "BEAMS PRO2-R-8": 8,
    "BEAMS PRO2-R-10": 10,
    "BEAMS MAX-R-2": 2,
    "BEAMS MAX-R-4": 4,
    "BEAMS MAX-R-6": 6,
    "BEAMS MAX-R-8": 8,
    "BEAMS MAX-R-10": 10,
    "BEAMS MAX-F-2": 2,
    "BEAMS MAX-F-4": 4,
    "BEAMS MAX-F-6": 6,
    "BEAMS MAX-F-8": 8,
    "BEAMS MAX-F-10": 10,
    "BEAMS MAX2-R-2": 2,
    "BEAMS MAX2-R-4": 4,
    "BEAMS MAX2-R-6": 6,
    "BEAMS MAX2-R-8": 8,
    "BEAMS MAX2-R-10": 10,
    "BEAMS MAX2-F-2": 2,
    "BEAMS MAX2-F-4": 4,
    "BEAMS MAX2-F-6": 6,
    "BEAMS MAX2-F-8": 8,
    "BEAMS MAX2-F-10": 10,
}


def clamp_channel(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


DLI_KEYS = (
    "dli",
    "DLI",
    "dailyDli",
    "dailyDLI",
    "daily_cycle_dli",
    "dailyCycleDli",
    "dailyCycleDLI",
    "totalDli",
    "totalDLI",
    "total_dli",
)

DAILY_CYCLE_KEYS = (
    "dailyCycle",
    "daily_cycle",
    "dailycycle",
    "currentDailyCycle",
    "current_daily_cycle",
    "currentCycle",
)

TIMEPOINT_KEYS = (
    "timepoint",
    "timePoint",
    "time_point",
    "currentTimepoint",
    "current_timepoint",
)


UPTIME_KEYS = (
    "uptime",
    "upTime",
    "up_time",
    "uptimeSec",
    "uptimeSecs",
    "uptimeSeconds",
    "uptime_sec",
    "uptime_seconds",
    "uptimeMs",
    "uptimeMillis",
    "uptimeMilliseconds",
    "systemUptime",
    "system_uptime",
    "runtime",
    "runTime",
    "run_time",
    "runningTime",
    "aliveTime",
    "alive_time",
)

BOOT_TIME_KEYS = (
    "bootTime",
    "boot_time",
    "boottime",
    "bootTimestamp",
    "boot_timestamp",
    "startedAt",
    "started_at",
)


PPFD_HEIGHTS_CM = (25, 35, 45)
PPFD_CONTEXT_TOKENS = (
    "ppfd",
    "par",
    "umol",
    "µmol",
    "photon",
    "photons",
)
PPFD_CHANNEL_LIST_KEYS = (
    "channels",
    "channelValues",
    "channel_values",
    "coefficients",
    "coefs",
    "values",
    "ppfd",
    "PPFD",
    "par",
    "PAR",
)
PPFD_HEIGHT_FIELD_KEYS = (
    "height",
    "heightCm",
    "height_cm",
    "distance",
    "distanceCm",
    "distance_cm",
    "cm",
)
PPFD_RATIO_CONTEXT_TOKENS = (
    "ratio",
    "factor",
    "scale",
    "distance",
    "height",
    "attenuation",
    "correction",
)
PPFD_RATIO_VALUE_KEYS = (
    "ratio",
    "factor",
    "scale",
    "value",
    "coefficient",
    "coef",
    "k",
)


def _height_from_value(value: Any) -> int | None:
    """Extract a centimetre height from API values like 25, '25', '@25cm'."""
    if isinstance(value, (int, float)):
        return int(value)
    if value is None:
        return None
    match = re.search(r"(\d+)", str(value))
    if match is None:
        return None
    return int(match.group(1))


def _is_ppfd_context_key(key: Any) -> bool:
    normalized = str(key).lower()
    return any(token in normalized for token in PPFD_CONTEXT_TOKENS)


def _is_ppfd_ratio_context_key(key: Any) -> bool:
    normalized = str(key).lower()
    return _is_ppfd_context_key(key) or any(token in normalized for token in PPFD_RATIO_CONTEXT_TOKENS)


def _key_matches_height(key: Any, height_cm: int) -> bool:
    """Return true for API keys such as 25, '25cm', '@25cm', 'ppfd25'."""
    normalized = str(key).lower()
    extracted = _height_from_value(normalized)
    if extracted != height_cm:
        return False
    compact = (
        normalized.replace("@", "")
        .replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace(".", "")
    )
    explicit = {
        str(height_cm),
        f"{height_cm}cm",
        f"cm{height_cm}",
        f"at{height_cm}",
        f"at{height_cm}cm",
        f"ppfd{height_cm}",
        f"ppfd{height_cm}cm",
        f"par{height_cm}",
        f"par{height_cm}cm",
    }
    return compact in explicit or any(token in compact for token in ("ppfd", "par", "umol", "µmol"))


def _as_float_list(value: Any) -> list[float]:
    """Convert a list/dict of channel coefficients to floats."""
    if isinstance(value, (list, tuple)):
        result: list[float] = []
        for item in value:
            number = _safe_float(item)
            if number is None:
                return []
            result.append(number)
        return result

    if isinstance(value, dict):
        for key in PPFD_CHANNEL_LIST_KEYS:
            if key in value:
                nested = _as_float_list(value.get(key))
                if nested:
                    return nested

        numbered: list[tuple[int, float]] = []
        for key, item in value.items():
            match = re.search(r"(\d+)", str(key))
            if match is None:
                continue
            number = _safe_float(item)
            if number is None:
                continue
            numbered.append((int(match.group(1)), number))
        if numbered:
            numbered.sort(key=lambda pair: pair[0])
            return [pair[1] for pair in numbered]

    return []


def _value_for_height_from_channel(channel: dict[str, Any], height_cm: int) -> float | None:
    """Extract one channel's PPFD coefficient for a given height from a channel dict.

    Controller payloads are not identical across firmware builds. Some expose
    height-specific PPFD directly on the channel object, while others keep it
    under nested LED records. For nested LED records we sum the per-LED values
    to get the channel coefficient for the requested height.
    """
    for key, value in channel.items():
        if _key_matches_height(key, height_cm):
            number = _safe_float(value)
            if number is not None:
                return number
            if isinstance(value, dict):
                for nested_key in ("value", "ppfd", "PPFD", "par", "PAR", "totalPPFD", "totalPpfd", "total_ppfd"):
                    number = _safe_float(value.get(nested_key))
                    if number is not None:
                        return number

    for ppfd_key in ("ppfd", "PPFD", "par", "PAR", "ppfdByHeight", "ppfd_by_height", "values"):
        nested = channel.get(ppfd_key)
        if isinstance(nested, dict):
            for key, value in nested.items():
                if _key_matches_height(key, height_cm):
                    number = _safe_float(value)
                    if number is not None:
                        return number
                    if isinstance(value, dict):
                        for value_key in ("value", "ppfd", "PPFD", "par", "PAR", "totalPPFD", "totalPpfd", "total_ppfd"):
                            number = _safe_float(value.get(value_key))
                            if number is not None:
                                return number
        elif isinstance(nested, list):
            for item in nested:
                if not isinstance(item, dict):
                    continue
                item_height = None
                for height_key in PPFD_HEIGHT_FIELD_KEYS:
                    if height_key in item:
                        item_height = _height_from_value(item.get(height_key))
                        break
                if item_height != height_cm:
                    continue
                for value_key in ("value", "ppfd", "PPFD", "par", "PAR", "totalPPFD", "totalPpfd", "total_ppfd"):
                    number = _safe_float(item.get(value_key))
                    if number is not None:
                        return number

    # Some /api/kit payloads expose detailed LED records inside a channel, e.g.
    # {"channels": [{"leds": [{"ppfd": {"25": ...}}, ...]}]}. Sum them so
    # @35/@45 can be calculated from real controller data instead of distance
    # approximations.
    for leds_key in ("leds", "LEDs", "diodes", "items"):
        leds = channel.get(leds_key)
        if not isinstance(leds, list):
            continue
        total = 0.0
        found = False
        for led in leds:
            if not isinstance(led, dict):
                continue
            number = _value_for_height_from_channel(led, height_cm)
            if number is None:
                continue
            total += number
            found = True
        if found:
            return total

    return None


def _find_ppfd_coefficients_for_height(
    value: Any,
    height_cm: int,
    *,
    max_depth: int = 7,
    in_ppfd_context: bool = False,
) -> list[float]:
    """Find per-channel PPFD coefficients for a height in BEAMS payloads."""
    if max_depth < 0:
        return []

    if isinstance(value, dict):
        # Common structure: {"ppfd": {"25": [..], "35": [..], "45": [..]}}
        for key, child in value.items():
            child_context = in_ppfd_context or _is_ppfd_context_key(key)
            if child_context and _key_matches_height(key, height_cm):
                result = _as_float_list(child)
                if result:
                    return result
                if isinstance(child, dict):
                    for nested_key in PPFD_CHANNEL_LIST_KEYS:
                        result = _as_float_list(child.get(nested_key))
                        if result:
                            return result

        # Common structure: {"25cm": {"channels": [..]}}
        if in_ppfd_context:
            for key, child in value.items():
                if _key_matches_height(key, height_cm):
                    result = _as_float_list(child)
                    if result:
                        return result

        # Common structure: {"channels": [{"ppfd": {"25": 12.3}}, ...]}
        for key in ("channels", "channelData", "channel_data", "leds"):
            channels = value.get(key)
            if isinstance(channels, list) and channels and all(isinstance(item, dict) for item in channels):
                coefficients: list[float] = []
                for channel in channels:
                    number = _value_for_height_from_channel(channel, height_cm)
                    if number is None:
                        coefficients = []
                        break
                    coefficients.append(number)
                if coefficients:
                    return coefficients

        for key, child in value.items():
            result = _find_ppfd_coefficients_for_height(
                child,
                height_cm,
                max_depth=max_depth - 1,
                in_ppfd_context=in_ppfd_context or _is_ppfd_context_key(key),
            )
            if result:
                return result

    elif isinstance(value, list):
        # Common structure: [{"height": 25, "channels": [..]}, ...]
        for item in value:
            if not isinstance(item, dict):
                continue
            item_height = None
            for height_key in PPFD_HEIGHT_FIELD_KEYS:
                if height_key in item:
                    item_height = _height_from_value(item.get(height_key))
                    break
            if item_height == height_cm:
                result = _as_float_list(item)
                if result:
                    return result

        for item in value:
            result = _find_ppfd_coefficients_for_height(
                item,
                height_cm,
                max_depth=max_depth - 1,
                in_ppfd_context=in_ppfd_context,
            )
            if result:
                return result

    return []


def _find_ppfd_ratio_for_height(
    value: Any,
    height_cm: int,
    *,
    max_depth: int = 7,
    in_ratio_context: bool = False,
) -> float | None:
    """Find a height-specific PPFD ratio/factor in controller payloads.

    Some firmware builds expose @35/@45 cm PPFD not as per-channel arrays, but as
    correction ratios relative to the native @25 cm totalPPFD. This searches only
    PPFD/distance/height-related subtrees to avoid treating unrelated values as
    PPFD corrections.
    """
    if max_depth < 0:
        return None

    if isinstance(value, dict):
        current_context = in_ratio_context

        # Common structures:
        # {"ppfdRatios": {"25": 1, "35": 0.8, "45": 0.7}}
        # {"distanceFactors": {"25cm": {"value": 1}, "35cm": {"value": 0.8}}}
        if current_context:
            for key, child in value.items():
                if not _key_matches_height(key, height_cm):
                    continue
                number = _safe_float(child)
                if number is not None:
                    return number
                if isinstance(child, dict):
                    for value_key in PPFD_RATIO_VALUE_KEYS:
                        number = _safe_float(child.get(value_key))
                        if number is not None:
                            return number

        # Common structures:
        # {"height": 35, "ratio": 0.8}
        item_height = None
        for height_key in PPFD_HEIGHT_FIELD_KEYS:
            if height_key in value:
                item_height = _height_from_value(value.get(height_key))
                break
        if current_context and item_height == height_cm:
            for value_key in PPFD_RATIO_VALUE_KEYS:
                number = _safe_float(value.get(value_key))
                if number is not None:
                    return number

        for key, child in value.items():
            found = _find_ppfd_ratio_for_height(
                child,
                height_cm,
                max_depth=max_depth - 1,
                in_ratio_context=current_context or _is_ppfd_ratio_context_key(key),
            )
            if found is not None:
                return found

    elif isinstance(value, list):
        for child in value:
            found = _find_ppfd_ratio_for_height(
                child,
                height_cm,
                max_depth=max_depth - 1,
                in_ratio_context=in_ratio_context,
            )
            if found is not None:
                return found

    return None


def _find_first_number_by_key(value: Any, keys: tuple[str, ...], *, max_depth: int = 5) -> float | None:
    """Recursively find the first numeric value whose key matches one of keys."""
    if max_depth < 0:
        return None
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                found = _safe_float(value.get(key))
                if found is not None:
                    return found
        for child in value.values():
            found = _find_first_number_by_key(child, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_first_number_by_key(child, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    return None


def _find_first_mapping_by_key(value: Any, keys: tuple[str, ...], *, max_depth: int = 5) -> dict[str, Any] | None:
    """Recursively find the first mapping stored under one of keys."""
    if max_depth < 0:
        return None
    if isinstance(value, dict):
        for key in keys:
            child = value.get(key)
            if isinstance(child, dict):
                return child
        for child in value.values():
            found = _find_first_mapping_by_key(child, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_first_mapping_by_key(child, keys, max_depth=max_depth - 1)
            if found is not None:
                return found
    return None


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def _parse_duration_seconds(value: Any) -> float | None:
    """Parse uptime-like values to seconds."""
    number = _safe_float(value)
    if number is not None:
        return number

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Examples: 01:02:03, 1 day, 01:02:03, 2 days 03:04:05.
    match = re.search(
        r"(?:(?P<days>\d+)\s*d(?:ay|ays)?[,\s]+)?(?P<hours>\d{1,2}):(?P<minutes>\d{2})(?::(?P<seconds>\d{2}))?",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        days = int(match.group("days") or 0)
        hours = int(match.group("hours") or 0)
        minutes = int(match.group("minutes") or 0)
        seconds = int(match.group("seconds") or 0)
        return float(days * 86400 + hours * 3600 + minutes * 60 + seconds)

    # Examples: 1d 2h 3m 4s, 2 hours 30 minutes.
    units = {
        "d": 86400,
        "day": 86400,
        "days": 86400,
        "h": 3600,
        "hour": 3600,
        "hours": 3600,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
    }
    total = 0.0
    found = False
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", text):
        multiplier = units.get(unit.lower())
        if multiplier is None:
            continue
        total += float(amount) * multiplier
        found = True
    if found:
        return total

    return None


def _seconds_since(value: Any) -> float | None:
    """Convert a boot timestamp to elapsed seconds."""
    number = _safe_float(value)
    if number is not None:
        # Treat large numeric values as Unix timestamps. Milliseconds are common in JS APIs.
        if number > 10_000_000_000:
            number = number / 1000
        if number > 1_000_000_000:
            return max((datetime.now(timezone.utc) - datetime.fromtimestamp(number, tz=timezone.utc)).total_seconds(), 0.0)
        return None

    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds(), 0.0)


def _find_uptime_seconds(value: Any, *, max_depth: int = 5, include_boot_time: bool = False) -> float | None:
    """Recursively find uptime in seconds in controller payloads."""
    if max_depth < 0:
        return None

    uptime_keys = {_normalized_key(key) for key in UPTIME_KEYS}
    boot_time_keys = {_normalized_key(key) for key in BOOT_TIME_KEYS}

    if isinstance(value, dict):
        for key, child in value.items():
            normalized = _normalized_key(key)
            if normalized in uptime_keys:
                seconds = _parse_duration_seconds(child)
                if seconds is not None:
                    if "ms" in normalized or "millis" in normalized or "milliseconds" in normalized:
                        seconds = seconds / 1000
                    return round(seconds, 0)
            if include_boot_time and normalized in boot_time_keys:
                seconds = _seconds_since(child)
                if seconds is not None:
                    return round(seconds, 0)

        for child in value.values():
            seconds = _find_uptime_seconds(child, max_depth=max_depth - 1, include_boot_time=include_boot_time)
            if seconds is not None:
                return seconds

    elif isinstance(value, list):
        for child in value:
            seconds = _find_uptime_seconds(child, max_depth=max_depth - 1, include_boot_time=include_boot_time)
            if seconds is not None:
                return seconds

    return None


def _nested_number(value: Any, path: tuple[str, ...]) -> float | None:
    """Return a numeric value from a nested dict path."""
    current = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _safe_float(current)


def _is_truthy(value: Any) -> bool:
    """Parse booleans stored as bool/string/number in controller JSON."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _cycle_points(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    """Return sorted daily-cycle points with time and channel arrays."""
    source = None
    for key in ("spectrums", "spectra", "points", "items"):
        value = cycle.get(key)
        if isinstance(value, list):
            source = value
            break
    if not source:
        return []

    points: list[dict[str, Any]] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        time_value = _safe_float(item.get("time"))
        channels = as_float_channels(item.get("channels"))
        if time_value is None or not channels:
            continue
        points.append({"time": max(min(float(time_value), float(SECONDS_PER_DAY)), 0.0), "channels": channels})

    points.sort(key=lambda item: item["time"])
    return points


class BeamsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """DataUpdateCoordinator for the BEAMS controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        api: BeamsLightApi,
    ) -> None:
        self.entry = entry
        self.api = api
        self._static_cache: dict[str, Any] | None = None
        self._manual_override: bool | None = None
        self._last_spectrum_option: str | None = entry.options.get(CONF_LAST_SPECTRUM)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.async_get_data()
        except BeamsApiError as err:
            raise UpdateFailed(f"Error communicating with BEAMS controller: {err}") from err

        if self._static_cache is None:
            self._static_cache = await self._async_get_static_data(data)

        if not data.get("manual_known", False):
            if self._manual_override is not None:
                data["manual"] = self._manual_override
            else:
                data["manual"] = self.entry.options.get(CONF_LAST_MODE) == MODE_MANUAL

        channel_count = self._detect_channel_count(data)
        channels = data.get("channels") or []
        if not channels:
            channels = [0.0] * channel_count
        elif len(channels) < channel_count:
            channels = [*channels, *([0.0] * (channel_count - len(channels)))]
        elif len(channels) > channel_count:
            channels = channels[:channel_count]

        return {
            **data,
            "channels": [clamp_channel(value) for value in channels],
            "channel_count": channel_count,
            **(self._static_cache or {}),
        }

    async def _async_get_static_data(self, data: dict[str, Any]) -> dict[str, Any]:
        network: dict[str, Any] = {}
        info: dict[str, Any] = {}
        ui: dict[str, Any] = {}
        math: Any = {}
        datetime_data: dict[str, Any] = {}
        spectrums: list[dict[str, Any]] = []

        try:
            network = await self.api.async_get_network()
        except BeamsApiError:
            network = {}
        try:
            info = await self.api.async_info()
        except BeamsApiError:
            info = {}
        try:
            ui = await self.api.async_get_ui()
        except BeamsApiError:
            ui = {}
        try:
            math = await self.api.async_get_math()
        except BeamsApiError:
            math = {}
        try:
            datetime_data = await self.api.async_get_datetime()
        except BeamsApiError:
            datetime_data = {}
        try:
            spectrums = self._normalize_spectrums(await self.api.async_get_spectrums())
        except BeamsApiError:
            spectrums = []

        return {
            "device_info": self._build_device_info(data, network, info),
            "network": network,
            "info": info,
            "ui": ui,
            "math": math,
            "datetime": datetime_data,
            "spectrums": spectrums,
        }

    def _build_device_info(
        self,
        data: dict[str, Any],
        network: dict[str, Any],
        info: dict[str, Any],
    ) -> dict[str, Any]:
        kit = data.get("kit") or {}
        ap = network.get("AP") if isinstance(network.get("AP"), dict) else {}
        general = info.get("general") if isinstance(info.get("general"), dict) else {}

        name = general.get("hostName") or ap.get("ssid") or self.entry.title
        model = kit.get("kit_name") or kit.get("device_name") or "BEAMS Light"
        device_id = general.get("deviceId") or name or self.entry.entry_id

        sw_version = general.get("swVersion")
        build_number = general.get("buildNumber")
        if sw_version and build_number:
            sw_version = f"{sw_version} / build {build_number}"
        elif build_number:
            sw_version = f"build {build_number}"

        return {
            "ident": str(device_id),
            "name": name,
            "model": model,
            "sw_version": sw_version,
            "hw_version": general.get("hwVersion"),
            "spec_alias": kit.get("spec_alias"),
        }

    def _detect_channel_count(self, data: dict[str, Any]) -> int:
        kit = data.get("kit") or {}
        kit_channels = kit.get("channels")
        if isinstance(kit_channels, list) and kit_channels:
            return len(kit_channels)
        channels = data.get("channels")
        if isinstance(channels, list) and channels:
            return len(channels)
        return DEFAULT_CHANNEL_COUNT

    def _normalize_spectrums(self, spectrums: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize gallery spectra and add stable HA option labels."""
        normalized: list[dict[str, Any]] = []
        names: dict[str, int] = {}
        for item in spectrums:
            name = str(item.get("name") or item.get("id") or "Spectrum").strip() or "Spectrum"
            names[name] = names.get(name, 0) + 1

        for item in spectrums:
            channels = as_float_channels(item.get("channels"))
            if not channels:
                continue
            spectrum_id = _safe_int(item.get("id"))
            name = str(item.get("name") or spectrum_id or "Spectrum").strip() or "Spectrum"
            option = name
            if names.get(name, 0) > 1 or spectrum_id is not None:
                # Always keep ID visible; it makes service calls and duplicate names unambiguous.
                option = f"{name} #{spectrum_id}" if spectrum_id is not None else name
            normalized.append(
                {
                    "id": spectrum_id,
                    "name": name,
                    "option": option,
                    "channels": channels,
                    "description": item.get("description") or "",
                    "favourite": bool(item.get("favourite", False)),
                    "readonly": bool(item.get("readonly", False)),
                    "type": item.get("type") or "",
                    "total_ppfd": _safe_float(item.get("totalPPFD")),
                }
            )
        return normalized

    @property
    def channels(self) -> list[float]:
        if not self.data:
            return []
        return list(self.data.get("channels") or [])

    @property
    def channel_count(self) -> int:
        if not self.data:
            return DEFAULT_CHANNEL_COUNT
        return int(self.data.get("channel_count") or DEFAULT_CHANNEL_COUNT)

    @property
    def is_manual(self) -> bool:
        if not self.data:
            return False
        return bool(self.data.get("manual", False))

    @property
    def mode(self) -> str:
        return MODE_MANUAL if self.is_manual else MODE_AUTO

    @property
    def spectrums(self) -> list[dict[str, Any]]:
        if not self.data:
            return []
        return list(self.data.get("spectrums") or [])

    @property
    def spectrum_options(self) -> list[str]:
        return [str(item["option"]) for item in self.spectrums if item.get("option")]

    @property
    def current_spectrum_option(self) -> str | None:
        matched = self.find_matching_spectrum(self.channels)
        if matched:
            return str(matched["option"])
        if self._last_spectrum_option in self.spectrum_options:
            return self._last_spectrum_option
        return None

    @property
    def current_spectrum(self) -> dict[str, Any] | None:
        option = self.current_spectrum_option
        if option is None:
            return None
        return self.find_spectrum(option)

    @property
    def current_daily_cycle(self) -> dict[str, Any]:
        """Return the current daily-cycle object from the controller payload when available."""
        data = self.data or {}
        for root_key in ("full", "state", "ui", "math"):
            root = data.get(root_key)
            if not isinstance(root, dict):
                continue
            daily_cycle = _find_first_mapping_by_key(root, DAILY_CYCLE_KEYS)
            if daily_cycle is not None:
                return daily_cycle
        return {}

    def _kit_channel_total_ppfd(self) -> list[float]:
        """Return native per-channel totalPPFD values from /api/kit."""
        kit = (self.data or {}).get("kit") or {}
        channels = kit.get("channels")
        if not isinstance(channels, list):
            return []

        result: list[float] = []
        for channel in channels:
            if isinstance(channel, dict):
                value = (
                    _safe_float(channel.get("totalPPFD"))
                    or _safe_float(channel.get("totalPpfd"))
                    or _safe_float(channel.get("total_ppfd"))
                    or _safe_float(channel.get("ppfd"))
                    or 0.0
                )
            else:
                value = _safe_float(channel, 0.0) or 0.0
            result.append(value)
        return result

    def _led_correction(self) -> float:
        """Return mathData.led_correction.value, defaulting to the native UI fallback of 1."""
        value = _nested_number((self.data or {}).get("math") or {}, ("led_correction", "value"))
        if value is None:
            return 1.0
        return value

    def _quest_ppfd_factor(self) -> float:
        """Return the same aquarium setup correction factor as the native UI qi()."""
        ui = (self.data or {}).get("ui") or {}
        quest_form = ui.get("questForm") if isinstance(ui.get("questForm"), dict) else None
        if not quest_form or not _is_truthy(quest_form.get("isComplete")):
            return 1.0

        length = _safe_float(quest_form.get("length"))
        width = _safe_float(quest_form.get("width"))
        if length is None or width is None:
            return 1.0

        # The native UI stores centimetres and converts them to metres with parseFloat(value) / 100.
        length_m = length / 100
        width_m = width / 100
        if length_m <= 0 or width_m <= 0:
            return 1.0

        assembly_count = 0.0
        led_counts = quest_form.get("ledCounts")
        if isinstance(led_counts, dict):
            for model, count in led_counts.items():
                assembly_count += BEAMS_ASSEMBLY_COUNTS.get(str(model), 0) * (_safe_float(count, 0.0) or 0.0)

        if assembly_count <= 0:
            return 1.0

        return 0.77 + (assembly_count / (length_m * width_m)) * 0.0185

    def _native_ppfd_25cm(self, channels: list[float]) -> float | None:
        """Calculate PPFD @25 cm the same way the native UI calculates totalPower."""
        total_ppfd = self._kit_channel_total_ppfd()
        if not total_ppfd:
            return None

        total = 0.0
        for index, value in enumerate(channels):
            if index >= len(total_ppfd):
                break
            total += total_ppfd[index] * value

        # The native UI rounds the per-point totalPower to three decimals.
        return round(total * self._quest_ppfd_factor(), 3)

    def _calculate_daily_cycle_dli(self, cycle: dict[str, Any]) -> float | None:
        """Calculate current daily-cycle DLI using the native web UI formula."""
        points = _cycle_points(cycle)
        if len(points) < 1:
            return None

        if len(points) == 1:
            expanded = [
                {**points[0], "time": 0.0},
                {**points[0], "time": float(SECONDS_PER_DAY)},
            ]
        else:
            # Native UI treats the daily cycle as cyclic:
            # last point at 00:00 -> all configured points -> first point at 24:00.
            expanded = [
                {**points[-1], "time": 0.0},
                *points,
                {**points[0], "time": float(SECONDS_PER_DAY)},
            ]

        total = 0.0
        for index, point in enumerate(expanded[:-1]):
            next_point = expanded[index + 1]
            duration = max(float(next_point["time"]) - float(point["time"]), 0.0)
            if duration <= 0:
                continue

            current_ppfd = self._native_ppfd_25cm(point["channels"])
            next_ppfd = self._native_ppfd_25cm(next_point["channels"])
            if current_ppfd is None or next_ppfd is None:
                return None

            total += ((current_ppfd + next_ppfd) / 2) * duration

        return (total / 1_000_000) * self._led_correction()

    @property
    def current_cycle_dli_source(self) -> str | None:
        """Human-readable source used for the current DLI value."""
        daily_cycle = self.current_daily_cycle
        if self._calculate_daily_cycle_dli(daily_cycle) is not None:
            return "calculated: dailyCycle.spectrums + kit.channels.totalPPFD + math.led_correction"

        value = _find_first_number_by_key(daily_cycle, DLI_KEYS, max_depth=3)
        if value is not None:
            return "api: dailyCycle.dli"

        data = self.data or {}
        for root_key in ("full", "state", "ui", "math"):
            root = data.get(root_key)
            if not isinstance(root, dict):
                continue
            value = _find_first_number_by_key(root, DLI_KEYS, max_depth=4)
            if value is not None:
                return f"api: {root_key}.dli"
        return None

    @property
    def current_cycle_dli(self) -> float | None:
        """DLI of the currently selected daily cycle, in mol/m²/day."""
        daily_cycle = self.current_daily_cycle

        # The native UI does not read DLI from a dedicated API field for the active cycle.
        # It calculates DLI from dailyCycle.spectrums, per-channel totalPPFD from /api/kit,
        # optional aquarium setup correction, and math.led_correction.value.
        calculated = self._calculate_daily_cycle_dli(daily_cycle)
        if calculated is not None:
            return calculated

        # Fallback for gallery/precomputed payloads from some firmware builds.
        value = _find_first_number_by_key(daily_cycle, DLI_KEYS, max_depth=3)
        if value is not None:
            return value

        # Some firmware builds expose the current-cycle DLI outside the dailyCycle object.
        data = self.data or {}
        for root_key in ("full", "state", "ui", "math"):
            root = data.get(root_key)
            if not isinstance(root, dict):
                continue
            value = _find_first_number_by_key(root, DLI_KEYS, max_depth=4)
            if value is not None:
                return value
        return None

    @property
    def dli(self) -> float | None:
        """Backward-compatible alias for current-cycle DLI."""
        return self.current_cycle_dli

    @property
    def timepoint(self) -> float | None:
        daily_cycle = self.current_daily_cycle
        value = _find_first_number_by_key(daily_cycle, TIMEPOINT_KEYS, max_depth=3)
        if value is not None:
            return value

        data = self.data or {}
        for root_key in ("full", "state"):
            root = data.get(root_key)
            if not isinstance(root, dict):
                continue
            value = _find_first_number_by_key(root, TIMEPOINT_KEYS, max_depth=4)
            if value is not None:
                return value
        return None

    def _ppfd_coefficients_for_height(self, height_cm: int) -> list[float]:
        """Return per-channel PPFD coefficients for a given mounting height."""
        data = self.data or {}
        for root_key in ("math", "kit", "ui", "full", "state"):
            root = data.get(root_key)
            result = _find_ppfd_coefficients_for_height(root, height_cm)
            if result:
                return result
        return []

    def _ppfd_ratio_for_height(self, height_cm: int) -> float | None:
        """Return a PPFD ratio/factor for a height relative to @25 cm, if exposed."""
        if height_cm == 25:
            return 1.0
        data = self.data or {}
        for root_key in ("math", "kit", "ui", "full", "state"):
            root = data.get(root_key)
            result = _find_ppfd_ratio_for_height(root, height_cm)
            if result is not None:
                # Accept only plausible relative factors. Values above 5 are almost
                # certainly raw PPFD or unrelated numeric fields, not ratios.
                if 0 < result <= 5:
                    return result
        return None

    def ppfd_cm(self, height_cm: int) -> float | None:
        """Calculate current PPFD at the requested height in µmol/m²/s."""
        channels = self.channels
        if not channels:
            return None

        coefficients = self._ppfd_coefficients_for_height(height_cm)
        if coefficients:
            total = 0.0
            for index, coefficient in enumerate(coefficients):
                if index >= len(channels):
                    break
                total += channels[index] * coefficient
            return round(total, 2)

        # The native web UI can calculate the current PPFD from /api/kit ->
        # channels[*].totalPPFD. On known firmware this is the @25 cm PPFD basis
        # used by the DLI calculation. Use it as the primary fallback for @25 cm.
        native_25 = self._native_ppfd_25cm(channels)
        if native_25 is not None:
            if height_cm == 25:
                return round(native_25, 2)

            # Do not use inverse-square fallback for @35/@45 cm: it is too low for
            # this extended aquarium light. Use only controller-provided ratios when
            # available; otherwise leave the value unknown instead of showing a wrong
            # estimate.
            ratio = self._ppfd_ratio_for_height(height_cm)
            if ratio is not None:
                return round(native_25 * ratio, 2)

        # The spectrum gallery exposes totalPPFD for saved spectra in some firmware builds.
        # Use it as a last fallback for @25cm when the current manual channels exactly
        # match a gallery spectrum.
        if height_cm == 25:
            spectrum = self.current_spectrum
            if spectrum is not None:
                total_ppfd = _safe_float(spectrum.get("total_ppfd"))
                if total_ppfd is not None:
                    return round(total_ppfd, 2)
        return None

    def ppfd_source_cm(self, height_cm: int) -> str | None:
        """Human-readable source used for a PPFD sensor."""
        channels = self.channels
        if not channels:
            return None
        coefficients = self._ppfd_coefficients_for_height(height_cm)
        if coefficients:
            return f"calculated: coefficients for @{height_cm}cm"
        native_25 = self._native_ppfd_25cm(channels)
        if native_25 is not None:
            if height_cm == 25:
                return "calculated: kit.channels.totalPPFD"
            ratio = self._ppfd_ratio_for_height(height_cm)
            if ratio is not None:
                return f"calculated: @25cm totalPPFD × controller ratio for @{height_cm}cm"
            if height_cm in (35, 45):
                return f"unavailable: no controller coefficients or ratio for @{height_cm}cm"
        if height_cm == 25 and self.current_spectrum is not None:
            total_ppfd = _safe_float(self.current_spectrum.get("total_ppfd"))
            if total_ppfd is not None:
                return "api: matched spectrum totalPPFD"
        return None

    @property
    def ppfd_25cm(self) -> float | None:
        return self.ppfd_cm(25)

    @property
    def ppfd_35cm(self) -> float | None:
        return self.ppfd_cm(35)

    @property
    def ppfd_45cm(self) -> float | None:
        return self.ppfd_cm(45)

    @property
    def max_power(self) -> float | None:
        kit = (self.data or {}).get("kit") or {}
        ui = kit.get("ui") if isinstance(kit.get("ui"), dict) else {}
        return _safe_float(ui.get("max_power"))

    @property
    def zero_power(self) -> float | None:
        kit = (self.data or {}).get("kit") or {}
        ui = kit.get("ui") if isinstance(kit.get("ui"), dict) else {}
        return _safe_float(ui.get("zero_power"))

    @property
    def estimated_power(self) -> float | None:
        """Estimate LED electrical power from kit.ui.max_channels_powers."""
        kit = (self.data or {}).get("kit") or {}
        ui = kit.get("ui") if isinstance(kit.get("ui"), dict) else {}
        max_channel_powers = ui.get("max_channels_powers")
        zero_power = _safe_float(ui.get("zero_power"), 0.0) or 0.0
        if not isinstance(max_channel_powers, list):
            return None
        total = zero_power
        for idx, max_power in enumerate(max_channel_powers):
            if idx >= len(self.channels):
                break
            value = _safe_float(max_power, 0.0) or 0.0
            total += value * self.channels[idx]
        return round(total, 2)


    @property
    def kit_name(self) -> str | None:
        """Return the light model name from /api/kit kit_name."""
        kit = (self.data or {}).get("kit") or {}
        value = kit.get("kit_name") or kit.get("device_name")
        if value is None:
            info = (self.data or {}).get("device_info") or {}
            value = info.get("model")
        return str(value) if value else None

    @property
    def uptime_seconds(self) -> float | None:
        """Controller uptime in seconds, when exposed by the controller API."""
        data = self.data or {}

        # /info is the most likely place for runtime diagnostics. It is fetched on every update
        # as runtime_info and also once as info in the static cache.
        for root_key in ("runtime_info", "info"):
            root = data.get(root_key)
            if isinstance(root, dict):
                value = _find_uptime_seconds(root, max_depth=5, include_boot_time=True)
                if value is not None:
                    return value

        # Some firmware builds may expose uptime directly in state payloads. Do not use
        # boot/start timestamp fallbacks here, because daily-cycle objects also contain
        # start-time-like fields.
        for root_key in ("state", "full", "kit"):
            root = data.get(root_key)
            if isinstance(root, dict):
                value = _find_uptime_seconds(root, max_depth=4, include_boot_time=False)
                if value is not None:
                    return value
        return None

    @property
    def device_name(self) -> str:
        info = (self.data or {}).get("device_info") or {}
        return info.get("name") or self.entry.title

    def get_default_manual_channels(self) -> list[float]:
        return [DEFAULT_MANUAL_VALUE] * self.channel_count

    def get_saved_manual_channels(self) -> list[float]:
        saved = self.entry.options.get(CONF_MANUAL_CHANNELS)
        if isinstance(saved, list) and saved:
            channels = [clamp_channel(float(value)) for value in saved]
            if len(channels) < self.channel_count:
                channels.extend([DEFAULT_MANUAL_VALUE] * (self.channel_count - len(channels)))
            return channels[: self.channel_count]
        return self.get_default_manual_channels()

    def save_last_mode(self, mode: str) -> None:
        options = dict(self.entry.options)
        options[CONF_LAST_MODE] = mode
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    def save_manual_channels(self, channels: list[float]) -> None:
        options = dict(self.entry.options)
        options[CONF_MANUAL_CHANNELS] = [clamp_channel(value) for value in channels]
        options[CONF_LAST_MODE] = MODE_MANUAL
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    def save_last_spectrum(self, option: str | None) -> None:
        options = dict(self.entry.options)
        if option is None:
            options.pop(CONF_LAST_SPECTRUM, None)
        else:
            options[CONF_LAST_SPECTRUM] = option
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    def find_spectrum(self, selector: str | int) -> dict[str, Any] | None:
        """Find a spectrum by option label, name, or numeric ID."""
        selector_str = str(selector).strip()
        selector_int = _safe_int(selector)
        selector_lower = selector_str.lower()
        for spectrum in self.spectrums:
            if selector_int is not None and spectrum.get("id") == selector_int:
                return spectrum
            if selector_str == str(spectrum.get("option")):
                return spectrum
            if selector_lower == str(spectrum.get("name") or "").lower():
                return spectrum
        return None

    def find_matching_spectrum(self, channels: list[float]) -> dict[str, Any] | None:
        """Return a gallery spectrum if current channels match it exactly enough."""
        if not channels:
            return None
        for spectrum in self.spectrums:
            spectrum_channels = list(spectrum.get("channels") or [])
            if len(spectrum_channels) != len(channels):
                continue
            if all(abs(float(a) - float(b)) <= SPECTRUM_MATCH_TOLERANCE for a, b in zip(channels, spectrum_channels)):
                return spectrum
        return None

    async def async_refresh_spectrums(self) -> None:
        """Reload spectrum gallery from the controller."""
        try:
            spectrums = self._normalize_spectrums(await self.api.async_get_spectrums())
        except BeamsApiError as err:
            raise HomeAssistantError(f"Cannot load BEAMS spectrum gallery: {err}") from err

        if self._static_cache is None:
            self._static_cache = {}
        self._static_cache["spectrums"] = spectrums
        if self.data is not None:
            self.async_set_updated_data({**self.data, "spectrums": spectrums})
        else:
            await self.async_request_refresh()

    async def async_apply_spectrum(self, selector: str | int) -> None:
        """Apply a spectrum from the controller gallery and switch to manual mode."""
        if not self.spectrums:
            await self.async_refresh_spectrums()
        spectrum = self.find_spectrum(selector)
        if spectrum is None:
            raise HomeAssistantError(f"BEAMS spectrum not found: {selector}")
        channels = list(spectrum.get("channels") or [])
        if not channels:
            raise HomeAssistantError(f"BEAMS spectrum has no channels: {selector}")
        option = str(spectrum.get("option") or spectrum.get("name") or selector)
        self._last_spectrum_option = option
        self.save_last_spectrum(option)
        await self.async_set_channels(channels, ensure_manual=True)

    async def async_set_mode(self, mode: str) -> None:
        if mode == MODE_MANUAL:
            channels = self.get_saved_manual_channels()
            if max(channels or [0.0]) <= 0.0001:
                channels = self.get_default_manual_channels()

            # The native BEAMS UI writes the manual channel buffer first
            # and only then switches state.manual=true. Keep the same order:
            # POST /api/channels/set -> POST /api/state/set {"manual": true}.
            self._manual_override = True
            await self.api.async_set_channels(channels)
            await self.api.async_set_manual(True)
            self.save_manual_channels(channels)
        elif mode == MODE_AUTO:
            if self.is_manual and any(value > 0.0001 for value in self.channels):
                self.save_manual_channels(self.channels)
            self._manual_override = False
            await self.api.async_set_manual(False)
            self.save_last_mode(MODE_AUTO)
        else:
            raise HomeAssistantError(f"Unsupported BEAMS mode: {mode}")
        await self.async_request_refresh()

    async def async_set_channels(self, channels: list[float], *, ensure_manual: bool = True) -> None:
        channels = [clamp_channel(value) for value in channels]
        if ensure_manual:
            # Match the native UI sequence when leaving automatic mode.
            self._manual_override = True
            await self.api.async_set_channels(channels)
            if not self.is_manual:
                await self.api.async_set_manual(True)
        else:
            await self.api.async_set_channels(channels)
        self.save_manual_channels(channels)
        await self.async_request_refresh()

    async def async_turn_off(self) -> None:
        if self.is_manual and any(value > 0.0001 for value in self.channels):
            self.save_manual_channels(self.channels)
        channels = [0.0] * self.channel_count
        self._manual_override = True
        self.save_last_mode(MODE_MANUAL)
        await self.api.async_set_channels(channels)
        if not self.is_manual:
            await self.api.async_set_manual(True)
        await self.async_request_refresh()

    async def async_turn_on(self, brightness: int | None = None) -> None:
        channels = self.get_saved_manual_channels()
        if max(channels or [0.0]) <= 0.0001:
            channels = self.get_default_manual_channels()
        if brightness is not None:
            target = max(min(brightness / 255.0, 1.0), 0.0)
            current_max = max(channels) if channels else 0.0
            if current_max <= 0.0001:
                channels = [target] * self.channel_count
            else:
                scale = target / current_max
                channels = [clamp_channel(value * scale) for value in channels]
        self._manual_override = True
        await self.api.async_set_channels(channels)
        if not self.is_manual:
            await self.api.async_set_manual(True)
        self.save_manual_channels(channels)
        await self.async_request_refresh()

    def channel_name(self, index: int) -> str:
        kit = (self.data or {}).get("kit") or {}
        kit_channels = kit.get("channels")
        if isinstance(kit_channels, list) and index < len(kit_channels):
            item = kit_channels[index]
            if isinstance(item, dict):
                leds = item.get("leds")
                if isinstance(leds, list) and leds:
                    led_types = [str(led.get("type")) for led in leds if isinstance(led, dict) and led.get("type")]
                    if led_types:
                        return " / ".join(led_types)
                return item.get("name") or item.get("title") or CHANNEL_NAMES[index if index < len(CHANNEL_NAMES) else -1]
        if index < len(CHANNEL_NAMES):
            return CHANNEL_NAMES[index]
        return f"Channel {index + 1}"
