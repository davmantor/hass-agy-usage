"""Sensor platform for Antigravity Usage integration."""

from __future__ import annotations

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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AntigravityUsageConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Antigravity Usage sensors."""
    coordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    if coordinator.data:
        if coordinator.data.get("tier") is not None:
            entities.append(AntigravityTierSensor(coordinator, entry))

        for group in coordinator.data.get("groups", []):
            key = group["key"]
            name = group["name"]
            if "weekly_remaining" in group:
                entities.append(AntigravityGroupSensor(coordinator, entry, key, "weekly_remaining", f"{name} Weekly", is_timestamp=False))
            if "fiveh_remaining" in group:
                entities.append(AntigravityGroupSensor(coordinator, entry, key, "fiveh_remaining", f"{name} 5h", is_timestamp=False))
            if "weekly_reset_time" in group:
                entities.append(AntigravityGroupSensor(coordinator, entry, key, "weekly_reset_time", f"{name} Weekly Reset", is_timestamp=True))
            if "fiveh_reset_time" in group:
                entities.append(AntigravityGroupSensor(coordinator, entry, key, "fiveh_reset_time", f"{name} 5h Reset", is_timestamp=True))

    async_add_entities(entities)


def _device_info(entry: AntigravityUsageConfigEntry) -> DeviceInfo:
    account_name = entry.data.get(CONF_ACCOUNT_NAME)
    subscription_level = entry.data.get(CONF_SUBSCRIPTION_LEVEL)
    parts = ["Antigravity Usage"]
    if account_name:
        parts.append(f"({account_name}")
        if subscription_level:
            parts.append(f"- {subscription_level})")
        else:
            parts[-1] += ")"
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=" ".join(parts),
        entry_type=DeviceEntryType.SERVICE,
    )


class AntigravityGroupSensor(CoordinatorEntity[AntigravityUsageCoordinator], SensorEntity):
    """Sensor for one quota window (weekly or 5h) of one model group."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AntigravityUsageCoordinator,
        entry: AntigravityUsageConfigEntry,
        group_key: str,
        field: str,
        name: str,
        *,
        is_timestamp: bool,
    ) -> None:
        super().__init__(coordinator)
        self._group_key = group_key
        self._field = field
        self._is_timestamp = is_timestamp
        self._attr_unique_id = f"{entry.entry_id}_{group_key}_{field}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)

        if is_timestamp:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._attr_icon = "mdi:timer-outline"
        else:
            self._attr_native_unit_of_measurement = "%"
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_icon = "mdi:gauge"

    def _group(self) -> dict[str, Any] | None:
        if self.coordinator.data is None:
            return None
        for group in self.coordinator.data.get("groups", []):
            if group["key"] == self._group_key:
                return group
        return None

    @property
    def available(self) -> bool:
        if not super().available or self.coordinator.data is None:
            return False
        g = self._group()
        return g is not None and g.get(self._field) is not None

    @property
    def native_value(self) -> Any:
        g = self._group()
        if g is None:
            return None
        val = g.get(self._field)
        if val is not None and self._is_timestamp:
            try:
                return datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return None
        return val


class AntigravityTierSensor(CoordinatorEntity[AntigravityUsageCoordinator], SensorEntity):
    """Sensor reporting the current Antigravity subscription tier."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-badge"

    def __init__(
        self,
        coordinator: AntigravityUsageCoordinator,
        entry: AntigravityUsageConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_tier"
        self._attr_name = "Subscription Tier"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("tier")
