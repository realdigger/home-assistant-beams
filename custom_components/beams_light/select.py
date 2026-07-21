"""Select platform for BEAMS Light."""
from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    MODE_AUTO,
    SPECTRUM_OPTION_MANUAL,
    SPECTRUM_OPTION_SERVICE,
)
from .coordinator import BeamsCoordinator
from .entity import BeamsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BeamsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [BeamsSpectrumSelect(coordinator), BeamsManualDurationSelect(coordinator)]
    )


class BeamsSpectrumSelect(BeamsEntity, SelectEntity):
    """Spectrum gallery select. Selecting an option applies it to the channels."""

    _attr_name = "Спектр"
    _attr_translation_key = "spectrum"
    _auto_option = "Авто: дневной цикл"

    def __init__(self, coordinator: BeamsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_spectrum"

    @property
    def options(self) -> list[str]:
        options = self.coordinator.spectrum_options
        if self.coordinator.mode == MODE_AUTO:
            return [self._auto_option, *options]
        if self.coordinator.manual_spectrum_mode is not None:
            return [self.coordinator.manual_spectrum_mode, *options]
        return options

    @property
    def current_option(self) -> str | None:
        if self.coordinator.mode == MODE_AUTO:
            return self._auto_option
        return self.coordinator.current_spectrum_option

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        spectrum = self.coordinator.current_spectrum
        if spectrum is None:
            return {"spectrums_count": len(self.coordinator.spectrums)}
        return {
            "spectrum_id": spectrum.get("id"),
            "spectrum_name": spectrum.get("name"),
            "total_ppfd": spectrum.get("total_ppfd"),
            "favourite": spectrum.get("favourite"),
            "readonly": spectrum.get("readonly"),
            "channels_percent": [round(float(value) * 100.0, 2) for value in spectrum.get("channels", [])],
            "spectrums_count": len(self.coordinator.spectrums),
        }

    async def async_select_option(self, option: str) -> None:
        if option == self._auto_option:
            await self.coordinator.async_set_mode(MODE_AUTO)
            return
        if option == SPECTRUM_OPTION_MANUAL:
            await self.coordinator.async_set_mode("manual")
            return
        if option == SPECTRUM_OPTION_SERVICE:
            await self.coordinator.async_activate_service_mode()
            return
        await self.coordinator.async_apply_spectrum(option)


class BeamsManualDurationSelect(BeamsEntity, SelectEntity):
    """Select the duration of a manual-mode session."""

    _attr_name = "Длительность ручного режима"
    _attr_translation_key = "manual_duration"

    def __init__(self, coordinator: BeamsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_manual_duration"

    @property
    def current_option(self) -> str:
        return f"{self.coordinator.manual_duration_hours} ч"

    @property
    def options(self) -> list[str]:
        return [f"{hours} ч" for hours in range(1, 7)]

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_manual_duration(int(option.split()[0]))
