"""Number platform for BEAMS Light channel controls."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_MANUAL
from .coordinator import BeamsCoordinator
from .entity import BeamsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BeamsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BeamsChannelNumber(coordinator, index) for index in range(coordinator.channel_count)]
    )


class BeamsChannelNumber(BeamsEntity, NumberEntity):
    """Per-channel percentage control."""

    _attr_native_min_value = 0.0
    _attr_native_max_value = 100.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: BeamsCoordinator, index: int) -> None:
        super().__init__(coordinator)
        self.index = index
        self._attr_unique_id = f"{coordinator.entry.entry_id}_channel_{index + 1}"
        self._attr_name = f"CH{index + 1} {coordinator.channel_name(index)}"

    @property
    def native_value(self) -> float | None:
        channels = self.coordinator.channels
        if self.index >= len(channels):
            return None
        return round(channels[self.index] * 100.0, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "channel": self.index + 1,
            "editable": self.coordinator.mode == MODE_MANUAL,
            "mode": self.coordinator.mode,
        }

    async def async_set_native_value(self, value: float) -> None:
        if self.coordinator.mode != MODE_MANUAL:
            raise HomeAssistantError("Switch BEAMS mode to manual before changing channels")
        channels = self.coordinator.channels
        if not channels:
            channels = self.coordinator.get_default_manual_channels()
        channels = list(channels)
        if self.index >= len(channels):
            raise HomeAssistantError(f"Channel {self.index + 1} is not available")
        channels[self.index] = min(max(float(value) / 100.0, 0.0), 1.0)
        await self.coordinator.async_set_channels(channels, ensure_manual=True)
