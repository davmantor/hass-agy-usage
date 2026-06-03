"""Sensor platform for Antigravity Usage integration."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AntigravityUsageConfigEntry, AntigravityUsageCoordinator
from .const import (
    CONF_ACCOUNT_NAME,
    CONF_SUBSCRIPTION_LEVEL,
    DOMAIN,
    SENSOR_DEFINITIONS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AntigravityUsageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Antigravity Usage sensors."""
    coordinator = entry.runtime_data
    
    # We create entities for all models present in the first data fetch
    entities = []
    if coordinator.data:
        for key, info in coordinator.data.items():
            entities.append(AntigravityModelSensor(coordinator, entry, key, info["name"]))
    
    async_add_entities(entities)


class AntigravityModelSensor(CoordinatorEntity[AntigravityUsageCoordinator], SensorEntity):
    """A sensor for a Antigravity usage metric."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AntigravityUsageCoordinator,
        entry: AntigravityUsageConfigEntry,
        key: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:brain"
        self._attr_state_class = SensorStateClass.MEASUREMENT

        # Build device name
        account_name = entry.data.get(CONF_ACCOUNT_NAME)
        subscription_level = entry.data.get(CONF_SUBSCRIPTION_LEVEL)

        device_name_parts = ["Antigravity Usage"]
        if account_name:
            device_name_parts.append(f"({account_name}")
            if subscription_level:
                device_name_parts.append(f"- {subscription_level})")
            else:
                device_name_parts[-1] += ")"
        device_name = " ".join(device_name_parts)

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=device_name,
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return True if the sensor value is present in coordinator data."""
        if not super().available:
            return False
        if self.coordinator.data is None:
            return False
        return self._key in self.coordinator.data

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        info = self.coordinator.data.get(self._key)
        if info:
            return info.get("value")
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        if self.coordinator.data is None:
            return {}
        info = self.coordinator.data.get(self._key)
        if info and "reset_time" in info:
            return {"reset_time": info["reset_time"]}
        return {}

