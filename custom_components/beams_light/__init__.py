"""BEAMS Light integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BeamsApiError, BeamsLightApi
from .const import (
    ATTR_CHANNELS,
    ATTR_ENTRY_ID,
    ATTR_MODE,
    ATTR_SPECTRUM,
    DOMAIN,
    MODE_AUTO,
    MODE_MANUAL,
    SERVICE_APPLY_SPECTRUM,
    SERVICE_REFRESH_SPECTRUMS,
    SERVICE_SET_CHANNELS,
    SERVICE_SET_MODE,
)
from .coordinator import BeamsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.NUMBER, Platform.SELECT, Platform.SENSOR]

SERVICE_SET_CHANNELS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHANNELS): vol.All(cv.ensure_list, [vol.Coerce(float)]),
        vol.Optional(ATTR_ENTRY_ID): str,
    }
)

SERVICE_SET_MODE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MODE): vol.In([MODE_AUTO, MODE_MANUAL]),
        vol.Optional(ATTR_ENTRY_ID): str,
    }
)

SERVICE_APPLY_SPECTRUM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_SPECTRUM): vol.Any(str, int),
        vol.Optional(ATTR_ENTRY_ID): str,
    }
)

SERVICE_REFRESH_SPECTRUMS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): str,
    }
)


def _get_target_coordinator(hass: HomeAssistant, call: ServiceCall) -> BeamsCoordinator:
    coordinators: dict[str, BeamsCoordinator] = hass.data.get(DOMAIN, {})
    target_entry_id = call.data.get(ATTR_ENTRY_ID)
    if target_entry_id:
        target = coordinators.get(target_entry_id)
        if target is None:
            raise HomeAssistantError(f"BEAMS controller is not loaded: {target_entry_id}")
        return target
    if len(coordinators) == 1:
        return next(iter(coordinators.values()))
    if not coordinators:
        raise HomeAssistantError("No BEAMS controller is loaded")
    raise HomeAssistantError("Multiple BEAMS controllers are loaded; provide entry_id")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up BEAMS Light from a config entry."""
    session = async_get_clientsession(hass)
    api = BeamsLightApi(session, entry.data[CONF_HOST])
    coordinator = BeamsCoordinator(hass, entry, api)

    try:
        await coordinator.async_config_entry_first_refresh()
    except BeamsApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_handle_set_channels(call: ServiceCall) -> None:
        channels_percent = [float(value) for value in call.data[ATTR_CHANNELS]]
        channels = [min(max(value / 100.0, 0.0), 1.0) for value in channels_percent]
        target = _get_target_coordinator(hass, call)
        await target.async_set_channels(channels, ensure_manual=True)

    async def async_handle_set_mode(call: ServiceCall) -> None:
        target = _get_target_coordinator(hass, call)
        await target.async_set_mode(call.data[ATTR_MODE])

    async def async_handle_apply_spectrum(call: ServiceCall) -> None:
        target = _get_target_coordinator(hass, call)
        await target.async_apply_spectrum(call.data[ATTR_SPECTRUM])

    async def async_handle_refresh_spectrums(call: ServiceCall) -> None:
        target = _get_target_coordinator(hass, call)
        await target.async_refresh_spectrums()

    if not hass.services.has_service(DOMAIN, SERVICE_SET_CHANNELS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_CHANNELS,
            async_handle_set_channels,
            schema=SERVICE_SET_CHANNELS_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_SET_MODE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_MODE,
            async_handle_set_mode,
            schema=SERVICE_SET_MODE_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_APPLY_SPECTRUM):
        hass.services.async_register(
            DOMAIN,
            SERVICE_APPLY_SPECTRUM,
            async_handle_apply_spectrum,
            schema=SERVICE_APPLY_SPECTRUM_SCHEMA,
        )

    if not hass.services.has_service(DOMAIN, SERVICE_REFRESH_SPECTRUMS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_REFRESH_SPECTRUMS,
            async_handle_refresh_spectrums,
            schema=SERVICE_REFRESH_SPECTRUMS_SCHEMA,
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            hass.services.async_remove(DOMAIN, SERVICE_SET_CHANNELS)
            hass.services.async_remove(DOMAIN, SERVICE_SET_MODE)
            hass.services.async_remove(DOMAIN, SERVICE_APPLY_SPECTRUM)
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_SPECTRUMS)
    return unload_ok
