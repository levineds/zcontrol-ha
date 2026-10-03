"""Binary sensor platform for Z-Control integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZControlConfigEntry
from .const import (
    DOMAIN,
    STATUS_AC_POWER,
    STATUS_BATTERY,
    STATUS_INPUT_1,
    STATUS_INPUT_2,
)
from .coordinator import ZControlCoordinator
from .entity import async_setup_entities

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ZControlBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes a Z-Control binary sensor entity."""

    status_name: str | None = None
    """The status name to look up in deviceStatusList (e.g., 'Input 1')."""


BINARY_SENSOR_DESCRIPTIONS: tuple[ZControlBinarySensorEntityDescription, ...] = (
    ZControlBinarySensorEntityDescription(
        key="online",
        name="Online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_registry_enabled_default=True,
    ),
    ZControlBinarySensorEntityDescription(
        key="input_1",
        name="Input 1",
        device_class=BinarySensorDeviceClass.PROBLEM,
        status_name=STATUS_INPUT_1,
        entity_registry_enabled_default=True,
    ),
    ZControlBinarySensorEntityDescription(
        key="input_2",
        name="Input 2",
        device_class=BinarySensorDeviceClass.PROBLEM,
        status_name=STATUS_INPUT_2,
        entity_registry_enabled_default=True,
    ),
    ZControlBinarySensorEntityDescription(
        key="ac_power",
        name="AC Power",
        device_class=BinarySensorDeviceClass.PROBLEM,
        status_name=STATUS_AC_POWER,
        entity_registry_enabled_default=True,
    ),
    ZControlBinarySensorEntityDescription(
        key="battery",
        name="Battery",
        device_class=BinarySensorDeviceClass.PROBLEM,
        status_name=STATUS_BATTERY,
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Control binary sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    def create_entities(device_id: str, device: dict[str, Any]) -> list[ZControlBinarySensor]:
        return [
            ZControlBinarySensor(
                coordinator=coordinator,
                device_id=device_id,
                device=device,
                description=description,
            )
            for description in BINARY_SENSOR_DESCRIPTIONS
        ]

    async_setup_entities(entry, async_add_entities, create_entities)


class ZControlBinarySensor(CoordinatorEntity[ZControlCoordinator], BinarySensorEntity):
    """Representation of a Z-Control binary sensor."""

    _attr_has_entity_name = True
    entity_description: ZControlBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: ZControlCoordinator,
        device_id: str,
        device: dict[str, Any],
        description: ZControlBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{description.key}"

        # Device info for grouping entities
        device_name = device.get("deviceName")
        if not device_name:  # Handle empty string or None
            device_name = f"Z-Control {device_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device_name,
            manufacturer="Zoeller",
            model=device.get("family", "Z-Control"),
            sw_version=device.get("firmwareVersion"),
            configuration_url="https://account.zcontrolcloud.com",
        )

    @property
    def _device_data(self) -> dict[str, Any] | None:
        """Get current device data from coordinator."""
        return self.coordinator.get_device(self._device_id)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._device_data is not None

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on (problem detected)."""
        device = self._device_data
        if device is None:
            return None

        key = self.entity_description.key

        # Online status - special case, inverted logic for CONNECTIVITY class
        if key == "online":
            # deviceOnline is 1 for online, 0 for offline
            online = device.get("deviceOnline")
            if online is not None:
                return bool(online)
            return None

        # Status-based sensors (Input 1, Input 2, AC Power, Battery)
        status_name = self.entity_description.status_name
        if status_name:
            status = self.coordinator.get_device_status(self._device_id, status_name)
            if status:
                # Check for fault or active alarm
                is_fault = status.get("isFault", 0)
                alarm_active = status.get("alarmActiveValue", 0)
                # Return True if there's a fault or alarm (problem detected)
                return bool(is_fault) or bool(alarm_active)

        return None
