"""Sensor platform for Z-Control integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from zoneinfo import ZoneInfo
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZControlConfigEntry
from .const import DOMAIN
from .coordinator import ZControlCoordinator

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="wifi_signal",
        name="WiFi Signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="alarm_count",
        name="Alarm Count",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="last_heartbeat",
        name="Last Heartbeat",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_registry_enabled_default=True,
    ),
    SensorEntityDescription(
        key="firmware",
        name="Firmware Version",
        entity_registry_enabled_default=False,
    ),
)


@dataclass(frozen=True, kw_only=True)
class ZControlDetailSensorDescription(SensorEntityDescription):
    """A numeric reading identified by its exact portal description."""

    detail_name: str
    value_unit: str = ""


DETAIL_SENSOR_DESCRIPTIONS: tuple[ZControlDetailSensorDescription, ...] = (
    ZControlDetailSensorDescription(
        key="battery_voltage",
        name="Battery Voltage",
        detail_name="Battery Voltage",
        value_unit="V",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZControlDetailSensorDescription(
        key="battery_current",
        name="Battery Current",
        detail_name="Battery Current",
        value_unit="A",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZControlDetailSensorDescription(
        key="dc_pump_current",
        name="DC Pump Current",
        detail_name="DC Pump Current",
        value_unit="A",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ZControlDetailSensorDescription(
        key="operational_float_count",
        name="Operational Float Count",
        detail_name="Operational Float Count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ZControlDetailSensorDescription(
        key="high_water_float_count",
        name="High Water Float Count",
        detail_name="High Water Float Count",
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ZControlDetailSensorDescription(
        key="pump_runtime",
        name="Pump Runtime",
        detail_name="Pump Runtime",
        value_unit="duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ZControlDetailSensorDescription(
        key="system_run_time",
        name="System Run Time",
        detail_name="System Run Time",
        value_unit="duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    ZControlDetailSensorDescription(
        key="up_time",
        name="Up Time",
        detail_name="Up Time",
        value_unit="duration",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        suggested_unit_of_measurement=UnitOfTime.DAYS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


def detail_descriptions(
    device: dict[str, Any],
) -> list[ZControlDetailSensorDescription]:
    """Create only readings that the cloud actually reports."""
    names = {
        row.get("description")
        for row in device.get("sensorDetails", [])
        if isinstance(row, dict)
    }
    return [
        description
        for description in DETAIL_SENSOR_DESCRIPTIONS
        if description.detail_name in names
    ]


def parse_detail_value(value: Any, unit: str) -> float | int | None:
    """Parse portal numbers or English duration text, rejecting unknown units."""
    if not isinstance(value, str):
        return None
    if unit == "duration":
        # The portal reports e.g. "1 Min" or "13 Hours, 40 Mins".
        pattern = r"(\d+)\s*(Days?|Hours?|Minutes?|Mins?|Seconds?|Secs?)"
        parts = re.findall(pattern, value, re.IGNORECASE)
        if not parts or re.sub(pattern, "", value, flags=re.IGNORECASE).strip(" ,"):
            return None
        factors = {"d": 1440, "h": 60, "m": 1, "s": 1 / 60}
        return sum(int(number) * factors[label[0].lower()] for number, label in parts)
    pattern = r"([+-]?\d+(?:\.\d+)?)" + (rf"\s*{re.escape(unit)}" if unit else "")
    match = re.fullmatch(pattern, value.strip())
    if match is None:
        return None
    number = float(match[1])
    if not math.isfinite(number):
        return None
    if not unit:
        return int(number) if number >= 0 and number.is_integer() else None
    return number


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Control sensors from a config entry."""
    coordinator = entry.runtime_data.coordinator

    entities: list[ZControlSensor] = []

    for device_id, device in coordinator.data.get("devices", {}).items():
        for description in (*SENSOR_DESCRIPTIONS, *detail_descriptions(device)):
            entities.append(
                ZControlSensor(
                    coordinator=coordinator,
                    device_id=device_id,
                    device=device,
                    description=description,
                )
            )

    async_add_entities(entities)


class ZControlSensor(CoordinatorEntity[ZControlCoordinator], SensorEntity):
    """Representation of a Z-Control sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ZControlCoordinator,
        device_id: str,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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
    def native_value(self) -> Any:
        """Return the sensor value."""
        device = self._device_data
        if device is None:
            return None

        if isinstance(self.entity_description, ZControlDetailSensorDescription):
            for row in device.get("sensorDetails", []):
                if (
                    isinstance(row, dict)
                    and row.get("description") == self.entity_description.detail_name
                ):
                    return parse_detail_value(
                        row.get("value"), self.entity_description.value_unit
                    )
            return None

        key = self.entity_description.key

        if key == "wifi_signal":
            # Get from deviceClass in first status entry
            status_list = device.get("deviceStatusList", [])
            if status_list:
                device_class = status_list[0].get("deviceClass", {})
                return device_class.get("rssiSignalStrength")
            return None

        if key == "alarm_count":
            return device.get("alarmCount", 0)

        if key == "last_heartbeat":
            # Parse the heartbeat timestamp
            heartbeat = device.get("lastHeartbeat")
            if heartbeat:
                # Try different formats
                for fmt in [
                    "%m-%d-%Y %I:%M:%S %p",  # "01-20-2026 6:20:41 PM"
                    "%Y-%m-%dT%H:%M:%S",      # ISO format
                    "%Y-%m-%dT%H:%M:%S.%f",   # ISO with microseconds
                ]:
                    try:
                        dt = datetime.strptime(heartbeat, fmt)
                        # API returns time in user's local timezone (from their account settings)
                        # Use HA's configured timezone
                        tz = ZoneInfo(self.coordinator.hass.config.time_zone)
                        return dt.replace(tzinfo=tz)
                    except ValueError:
                        continue
            return None

        if key == "firmware":
            return device.get("firmwareVersion")

        return None
