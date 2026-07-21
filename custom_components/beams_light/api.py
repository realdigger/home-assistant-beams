"""Local API client for BEAMS controllers."""
from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urlparse

from aiohttp import ClientError, ClientResponse, ClientSession

from .const import DEFAULT_TIMEOUT


class BeamsApiError(Exception):
    """Base API error."""


class BeamsCannotConnect(BeamsApiError):
    """Raised when the controller is unreachable."""


class BeamsInvalidResponse(BeamsApiError):
    """Raised when the controller returns invalid data."""


def normalize_base_url(host: str) -> str:
    """Normalize a host/IP/base URL to a URL without trailing slash."""
    host = host.strip()
    if not host:
        raise BeamsCannotConnect("Empty host")
    if not host.startswith(("http://", "https://")):
        host = f"http://{host}"
    parsed = urlparse(host)
    if not parsed.hostname:
        raise BeamsCannotConnect(f"Invalid host: {host}")
    return host.rstrip("/")


def as_float_channels(value: Any) -> list[float]:
    """Convert any channel-like value to a clamped 0..1 float list."""
    if not isinstance(value, list):
        return []
    result: list[float] = []
    for item in value:
        try:
            channel = float(item)
        except (TypeError, ValueError):
            channel = 0.0
        result.append(min(max(channel, 0.0), 1.0))
    return result


def as_bool(value: Any) -> bool:
    """Parse boolean values returned as JSON booleans, numbers, or strings."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class BeamsLightApi:
    """Client for the BEAMS REST API used by the built-in web UI."""

    def __init__(self, session: ClientSession, base_url: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.session = session
        self.base_url = normalize_base_url(base_url)
        self.api_url = f"{self.base_url}/api"
        self.timeout = timeout

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_data: dict[str, Any] | None = None,
        api: bool = True,
    ) -> Any:
        """Run an API request and decode JSON or text."""
        path = path.lstrip("/")
        url = f"{self.api_url if api else self.base_url}/{path}"
        try:
            async with asyncio.timeout(self.timeout):
                response = await self.session.request(
                    method,
                    url,
                    json=json_data,
                    headers={"Content-Type": "application/json"},
                )
                return await self._decode_response(response)
        except TimeoutError as err:
            raise BeamsCannotConnect(f"Timeout connecting to {url}") from err
        except ClientError as err:
            raise BeamsCannotConnect(f"Error connecting to {url}: {err}") from err

    async def _decode_response(self, response: ClientResponse) -> Any:
        """Decode response and raise on HTTP errors."""
        text = await response.text()
        if response.status < 200 or response.status >= 300:
            raise BeamsCannotConnect(f"HTTP {response.status}: {text[:200]}")
        if not text:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type.lower():
            try:
                return json.loads(text)
            except json.JSONDecodeError as err:
                raise BeamsInvalidResponse(f"Invalid JSON: {text[:200]}") from err
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    async def async_get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        """Run a GET request against /api."""
        if query:
            from urllib.parse import urlencode

            path = f"{path}?{urlencode(query)}"
        return await self._request("GET", path)

    async def async_post(self, path: str, payload: dict[str, Any] | None = None) -> Any:
        """Run a POST request against /api."""
        return await self._request("POST", path, json_data=payload or {})

    async def async_info(self) -> dict[str, Any]:
        """Get root /info, not /api/info."""
        data = await self._request("GET", "info", api=False)
        return data if isinstance(data, dict) else {}

    async def async_get_kit(self) -> dict[str, Any]:
        data = await self.async_get("kit")
        return data if isinstance(data, dict) else {}

    async def async_get_math(self) -> Any:
        data = await self.async_get("math/get")
        return data if isinstance(data, (dict, list)) else {}

    async def async_get_ui(self) -> dict[str, Any]:
        data = await self.async_get("ui/get")
        return data if isinstance(data, dict) else {}

    async def async_get_network(self) -> dict[str, Any]:
        data = await self.async_get("system/network/getwlanconfig")
        return data if isinstance(data, dict) else {}

    async def async_get_state(self) -> dict[str, Any]:
        data = await self.async_get("state/get")
        return data if isinstance(data, dict) else {}

    async def async_get_full_state(self) -> dict[str, Any]:
        data = await self.async_get("state/full")
        return data if isinstance(data, dict) else {}

    async def async_get_channels(self) -> list[float]:
        data = await self.async_get("channels/get")
        if not isinstance(data, dict):
            return []
        return as_float_channels(data.get("channels"))

    async def async_get_spectrums(self) -> list[dict[str, Any]]:
        """Get spectrum gallery entries from /api/spectrums."""
        data = await self.async_get("spectrums")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    async def async_get_leds(self) -> list[dict[str, Any]]:
        """Get LED spectral curves used by the controller UI."""
        data = await self.async_get("led")
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch the practical state used by Home Assistant."""
        state: dict[str, Any] = {}
        full: dict[str, Any] = {}
        channels: list[float] = []

        errors: list[Exception] = []

        try:
            state = await self.async_get_state()
        except BeamsApiError as err:
            errors.append(err)

        try:
            full = await self.async_get_full_state()
        except BeamsApiError:
            full = {}

        channels = as_float_channels(full.get("channels")) or as_float_channels(state.get("channels"))
        if not channels:
            try:
                channels = await self.async_get_channels()
            except BeamsApiError as err:
                errors.append(err)

        if not state and not full and not channels:
            if errors:
                raise BeamsCannotConnect(str(errors[-1])) from errors[-1]
            raise BeamsCannotConnect("No usable data returned by the controller")


        manual_keys = ("manual", "isManual", "manualMode")
        manual_known = any(key in state for key in manual_keys) or any(key in full for key in manual_keys)
        manual = any(
            as_bool(source.get(key))
            for source in (state, full)
            for key in manual_keys
            if key in source
        )

        return {
            "state": state,
            "full": full,
            "channels": channels,
            "manual": manual,
            "manual_known": manual_known,
            "long_cycle": as_bool(state.get("longCycle", False)),
            "slave": as_bool(state.get("slave", False)),
        }

    async def async_set_manual(self, manual: bool) -> None:
        await self.async_post("state/set", {"manual": bool(manual)})

    async def async_set_channels(self, channels: list[float]) -> None:
        await self.async_post("channels/set", {"channels": as_float_channels(channels)})

    async def async_set_daily_cycle(self, cycle: dict[str, Any]) -> None:
        await self.async_post("state/dailycycle/set", cycle)
