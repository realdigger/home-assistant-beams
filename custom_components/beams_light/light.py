"""Light platform for BEAMS Light."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_CHANNELS_PERCENT, DOMAIN
from .coordinator import BeamsCoordinator
from .entity import BeamsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BeamsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BeamsLight(coordinator)])


class BeamsLight(BeamsEntity, LightEntity):
    """Main BEAMS light entity."""

    _attr_name = None
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS

    def __init__(self, coordinator: BeamsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_light"

    @property
    def is_on(self) -> bool:
        return any(value > 0.0001 for value in self.coordinator.channels)

    @property
    def brightness(self) -> int | None:
        channels = self.coordinator.channels
        if not channels:
            return 0
        return round(max(channels) * 255)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        channels = self.coordinator.channels
        attrs: dict[str, Any] = {
            "mode": self.coordinator.mode,
            ATTR_CHANNELS_PERCENT: [round(value * 100, 2) for value in channels],
            "long_cycle": bool((self.coordinator.data or {}).get("long_cycle", False)),
            "slave": bool((self.coordinator.data or {}).get("slave", False)),
        }
        if self.coordinator.dli is not None:
            attrs["dli"] = round(self.coordinator.dli, 3)
        if self.coordinator.estimated_power is not None:
            attrs["estimated_power_w"] = self.coordinator.estimated_power
        spectrum = self.coordinator.current_spectrum
        if spectrum is not None:
            attrs["spectrum"] = spectrum.get("option")
            attrs["spectrum_id"] = spectrum.get("id")
            attrs["spectrum_total_ppfd"] = spectrum.get("total_ppfd")
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_turn_on(kwargs.get(ATTR_BRIGHTNESS))

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_turn_off()
