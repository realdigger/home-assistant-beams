"""Base entity helpers for BEAMS Light."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BeamsCoordinator


class BeamsEntity(CoordinatorEntity[BeamsCoordinator]):
    """Base BEAMS entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: BeamsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        info: dict[str, Any] = (self.coordinator.data or {}).get("device_info") or {}
        ident = str(info.get("ident") or self.coordinator.entry.entry_id)
        device_info: DeviceInfo = {
            "identifiers": {(DOMAIN, ident)},
            "manufacturer": "Beautiful Reef",
            "name": info.get("name") or self.coordinator.entry.title,
            "model": info.get("model") or "BEAMS Light",
        }
        if info.get("sw_version"):
            device_info["sw_version"] = info["sw_version"]
        if info.get("hw_version"):
            device_info["hw_version"] = info["hw_version"]
        if info.get("model_id"):
            device_info["model_id"] = info["model_id"]
        return device_info
