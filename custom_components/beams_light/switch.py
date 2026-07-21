"""Mode switch platform for BEAMS Light."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_AUTO, MODE_MANUAL
from .coordinator import BeamsCoordinator
from .entity import BeamsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BEAMS manual mode switch."""
    coordinator: BeamsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BeamsModeSwitch(coordinator)])


class BeamsModeSwitch(BeamsEntity, SwitchEntity):
    """Switch between automatic and manual BEAMS mode."""

    _attr_name = "Manual mode"
    _attr_translation_key = "manual_mode"

    def __init__(self, coordinator: BeamsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_mode"

    @property
    def is_on(self) -> bool:
        return self.coordinator.mode == MODE_MANUAL

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_mode(MODE_MANUAL)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_set_mode(MODE_AUTO)
