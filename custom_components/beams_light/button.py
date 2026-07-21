"""Button platform for BEAMS Light."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BeamsCoordinator
from .entity import BeamsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the BEAMS spectrum-refresh button."""
    coordinator: BeamsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BeamsRefreshSpectrumsButton(coordinator)])


class BeamsRefreshSpectrumsButton(BeamsEntity, ButtonEntity):
    """Refresh the spectrum gallery from the controller."""

    _attr_name = "Обновить спектры"
    _attr_translation_key = "refresh_spectrums"

    def __init__(self, coordinator: BeamsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_refresh_spectrums"

    async def async_press(self) -> None:
        """Fetch the current spectrum gallery."""
        await self.coordinator.async_refresh_spectrums()
