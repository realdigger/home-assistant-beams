"""BEAMS Light integration."""
from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

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

FRONTEND_URL = "/beams_light_static/beams-channel-card.js"
FRONTEND_DATA_KEY = f"{DOMAIN}_frontend_registered"

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate the former controllable light into a read-only binary sensor."""
    if entry.version > 12:
        return False
    if entry.version < 2:
        entity_registry = er.async_get(hass)
        old_entity_id = entity_registry.async_get_entity_id(
            Platform.LIGHT,
            DOMAIN,
            f"{entry.entry_id}_light",
        )
        if old_entity_id is not None:
            entity_registry.async_remove(old_entity_id)
    if entry.version < 3:
        entity_registry = er.async_get(hass)
        old_entity_id = entity_registry.async_get_entity_id(
            Platform.SELECT,
            DOMAIN,
            f"{entry.entry_id}_mode",
        )
        if old_entity_id is not None:
            entity_registry.async_remove(old_entity_id)
    if entry.version < 5:
        entity_registry = er.async_get(hass)
        old_unique_id = f"{entry.entry_id}_software_scripts"
        for entity_id, registry_entry in entity_registry.entities.items():
            if registry_entry.unique_id == old_unique_id:
                entity_registry.async_remove(entity_id)
                break
    if entry.version < 6:
        entity_registry = er.async_get(hass)
        old_entity_id = entity_registry.async_get_entity_id(
            Platform.BUTTON,
            DOMAIN,
            f"{entry.entry_id}_service_mode",
        )
        if old_entity_id is not None:
            entity_registry.async_remove(old_entity_id)
    if entry.version < 7:
        entity_registry = er.async_get(hass)
        service_mode_unique_id = f"{entry.entry_id}_service_mode"
        manual_mode_unique_id = f"{entry.entry_id}_mode"
        for entity_id, registry_entry in entity_registry.entities.items():
            if registry_entry.unique_id == service_mode_unique_id and entity_id.startswith("button."):
                entity_registry.async_remove(entity_id)
            elif registry_entry.unique_id == manual_mode_unique_id:
                entity_registry.async_update_entity(entity_id, original_name=None)
    if entry.version < 8:
        entity_registry = er.async_get(hass)
        names_by_unique_id = {
            f"{entry.entry_id}_mode": "Ручной режим",
            f"{entry.entry_id}_service_mode": "Сервисный режим",
        }
        for entity_id, registry_entry in entity_registry.entities.items():
            name = names_by_unique_id.get(registry_entry.unique_id)
            if name is not None:
                entity_registry.async_update_entity(entity_id, original_name=name)
    if entry.version < 9:
        entity_registry = er.async_get(hass)
        spectrum_unique_id = f"{entry.entry_id}_spectrum"
        for entity_id, registry_entry in entity_registry.entities.items():
            if registry_entry.unique_id == spectrum_unique_id:
                entity_registry.async_update_entity(entity_id, original_name="Спектр")
                break
    if entry.version < 10:
        entity_registry = er.async_get(hass)
        brightness_unique_id = f"{entry.entry_id}_brightness"
        for entity_id, registry_entry in entity_registry.entities.items():
            if registry_entry.unique_id == brightness_unique_id:
                entity_registry.async_update_entity(entity_id, original_name="Яркость")
                break
    if entry.version < 11:
        entity_registry = er.async_get(hass)
        remaining_unique_id = f"{entry.entry_id}_manual_mode_remaining"
        for entity_id, registry_entry in entity_registry.entities.items():
            if registry_entry.unique_id == remaining_unique_id:
                entity_registry.async_update_entity(
                    entity_id,
                    original_name="До сброса ручного режима",
                )
                break
    if entry.version < 12:
        entity_registry = er.async_get(hass)
        duration_unique_id = f"{entry.entry_id}_manual_duration"
        for entity_id, registry_entry in entity_registry.entities.items():
            if registry_entry.unique_id == duration_unique_id:
                entity_registry.async_update_entity(
                    entity_id,
                    original_name="Длительность ручного режима",
                )
                break
    hass.config_entries.async_update_entry(entry, version=12, minor_version=entry.minor_version)
    return True


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    """Register Lovelace resources before config entries are initialized."""
    if not hass.data.get(FRONTEND_DATA_KEY):
        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    "/beams_light_static",
                    str(Path(__file__).parent / "frontend"),
                    cache_headers=False,
                )
            ]
        )
        frontend.add_extra_js_url(hass, FRONTEND_URL)
        hass.data[FRONTEND_DATA_KEY] = True
    return True


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

    entity_registry = er.async_get(hass)
    brightness_unique_id = f"{entry.entry_id}_brightness"
    for entity_id, registry_entry in entity_registry.entities.items():
        if (
            registry_entry.unique_id == brightness_unique_id
            and registry_entry.original_name != "Яркость"
        ):
            entity_registry.async_update_entity(entity_id, original_name="Яркость")
            break

    remaining_unique_id = f"{entry.entry_id}_manual_mode_remaining"
    for entity_id, registry_entry in entity_registry.entities.items():
        if (
            registry_entry.unique_id == remaining_unique_id
            and registry_entry.original_name != "До сброса ручного режима"
        ):
            entity_registry.async_update_entity(
                entity_id,
                original_name="До сброса ручного режима",
            )
            break

    duration_unique_id = f"{entry.entry_id}_manual_duration"
    for entity_id, registry_entry in entity_registry.entities.items():
        if (
            registry_entry.unique_id == duration_unique_id
            and registry_entry.original_name != "Длительность ручного режима"
        ):
            entity_registry.async_update_entity(
                entity_id,
                original_name="Длительность ручного режима",
            )
            break

    device_info = (coordinator.data or {}).get("device_info") or {}
    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, str(device_info.get("ident") or entry.entry_id))}
    )
    if device is not None:
        device_registry.async_update_device(
            device.id,
            model_id=device_info.get("model_id"),
            serial_number=device_info.get("serial_number"),
            sw_version=device_info.get("sw_version"),
            hw_version=device_info.get("hw_version"),
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def async_handle_set_channels(call: ServiceCall) -> None:
        target = _get_target_coordinator(hass, call)
        channels_percent = [float(value) for value in call.data[ATTR_CHANNELS]]
        if len(channels_percent) != target.channel_count:
            raise HomeAssistantError(
                f"Expected {target.channel_count} channel values, got {len(channels_percent)}"
            )
        channels = [min(max(value / 100.0, 0.0), 1.0) for value in channels_percent]
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
            frontend.remove_extra_js_url(hass, FRONTEND_URL)
            hass.data.pop(FRONTEND_DATA_KEY, None)
            hass.services.async_remove(DOMAIN, SERVICE_SET_CHANNELS)
            hass.services.async_remove(DOMAIN, SERVICE_SET_MODE)
            hass.services.async_remove(DOMAIN, SERVICE_APPLY_SPECTRUM)
            hass.services.async_remove(DOMAIN, SERVICE_REFRESH_SPECTRUMS)
    return unload_ok
