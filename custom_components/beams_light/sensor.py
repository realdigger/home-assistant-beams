"""Sensor platform for BEAMS Light."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import BeamsCoordinator
from .entity import BeamsEntity


@dataclass(frozen=True, kw_only=True)
class BeamsSensorEntityDescription(SensorEntityDescription):
    """Description for a BEAMS sensor."""

    value_fn: Callable[[BeamsCoordinator], Any]


def _format_uptime(seconds: float | None) -> str | None:
    """Format uptime as days, hours, and minutes."""
    if seconds is None:
        return None
    total = max(int(seconds), 0)
    days = total // 86400
    hours = (total % 86400) // 3600
    minutes = (total % 3600) // 60
    return f"{days} д {hours} ч {minutes:02d} мин"


def _format_ppfd(value: float | None) -> int | None:
    """Format PPFD as a whole number for display."""
    if value is None:
        return None
    return int(max(float(value), 0.0) + 0.5)


def _format_cycle_timepoint(seconds: float | None) -> str | None:
    """Format a daily-cycle timepoint as hours and minutes."""
    if seconds is None:
        return None
    total = max(int(seconds), 0)
    if total >= 86400:
        hours = 24
        minutes = 0
    else:
        total = total % 86400
        hours = total // 3600
        minutes = (total % 3600) // 60
    return f"{hours} ч {minutes:02d} мин"


def _format_manual_session_remaining(seconds: float | None) -> str | None:
    """Format the remaining manual-mode session time."""
    if seconds is None:
        return None
    total_minutes = max(int(seconds) // 60, 0)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours} ч {minutes:02d} мин"


SENSORS: tuple[BeamsSensorEntityDescription, ...] = (
    BeamsSensorEntityDescription(
        key="current_cycle_dli",
        translation_key="current_cycle_dli",
        name="Current cycle DLI",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: round(coordinator.current_cycle_dli, 1) if coordinator.current_cycle_dli is not None else None,
    ),
    BeamsSensorEntityDescription(
        key="ppfd_25cm",
        translation_key="ppfd_25cm",
        name="PPFD @25 cm",
        native_unit_of_measurement="µmol/m²/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: _format_ppfd(coordinator.ppfd_25cm),
    ),
    BeamsSensorEntityDescription(
        key="ppfd_35cm",
        translation_key="ppfd_35cm",
        name="PPFD @35 cm",
        native_unit_of_measurement="µmol/m²/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: _format_ppfd(coordinator.ppfd_35cm),
    ),
    BeamsSensorEntityDescription(
        key="ppfd_45cm",
        translation_key="ppfd_45cm",
        name="PPFD @45 cm",
        native_unit_of_measurement="µmol/m²/s",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: _format_ppfd(coordinator.ppfd_45cm),
    ),

    BeamsSensorEntityDescription(
        key="kit_name",
        translation_key="kit_name",
        name="Light model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.kit_name,
    ),
    BeamsSensorEntityDescription(
        key="uptime",
        translation_key="uptime",
        name="Uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: _format_uptime(coordinator.uptime_seconds),
    ),
    BeamsSensorEntityDescription(
        key="estimated_power",
        translation_key="estimated_power",
        name="Estimated power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda coordinator: coordinator.estimated_power,
    ),
    BeamsSensorEntityDescription(
        key="timepoint",
        translation_key="timepoint",
        name="Cycle timepoint",
        value_fn=lambda coordinator: _format_cycle_timepoint(coordinator.timepoint),
    ),
    BeamsSensorEntityDescription(
        key="manual_mode_remaining",
        translation_key="manual_mode_remaining",
        name="До сброса ручного режима",
        value_fn=lambda coordinator: _format_manual_session_remaining(
            coordinator.manual_session_remaining_seconds
        ),
    ),
    BeamsSensorEntityDescription(
        key="light_uniformity",
        translation_key="light_uniformity",
        name="Light uniformity",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.light_uniformity,
    ),
    BeamsSensorEntityDescription(
        key="assembly_count",
        translation_key="assembly_count",
        name="Assembly count",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.assembly_count,
    ),
    BeamsSensorEntityDescription(
        key="controller_id",
        translation_key="controller_id",
        name="Controller ID",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda coordinator: coordinator.controller_id,
    ),
    *(
        BeamsSensorEntityDescription(
            key=f"software_{component}",
            translation_key=f"software_{component}",
            name=name,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda coordinator, component=component: coordinator.software_version(component),
        )
        for component, name in (
            ("kernel", "Kernel version"),
            ("lcs", "LCS version"),
            ("os", "OS version"),
            ("ui", "TrueSpectrum version"),
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BeamsCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BeamsSensor(coordinator, description) for description in SENSORS])


class BeamsSensor(BeamsEntity, SensorEntity):
    """BEAMS diagnostic/state sensor."""

    entity_description: BeamsSensorEntityDescription

    def __init__(self, coordinator: BeamsCoordinator, description: BeamsSensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "current_cycle_dli":
            return {"source": self.coordinator.current_cycle_dli_source}
        if self.entity_description.key.startswith("ppfd_"):
            try:
                height_cm = int(self.entity_description.key.split("_")[1].replace("cm", ""))
            except (IndexError, ValueError):
                return None
            return {"source": self.coordinator.ppfd_source_cm(height_cm)}
        if self.entity_description.key == "light_uniformity":
            return {"source": "calculated: native UI @25cm geometry model"}
        if self.entity_description.key.startswith("software_"):
            component = self.entity_description.key.removeprefix("software_")
            hash_value = self.coordinator.software_hash(component)
            return {"hash": hash_value} if hash_value is not None else None
        return None
