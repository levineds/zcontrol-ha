"""Button platform for Z-Control integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Coroutine

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ZControlConfigEntry
from .api import ZControlApiClient
from .const import DOMAIN
from .coordinator import ZControlCoordinator
from .entity import async_setup_entities

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class ZControlButtonEntityDescription(ButtonEntityDescription):
    """Describes a Z-Control button entity."""

    press_fn: str
    """Method name on ZControlApiClient to call (e.g., 'silence_alarm')."""


BUTTON_DESCRIPTIONS: tuple[ZControlButtonEntityDescription, ...] = (
    ZControlButtonEntityDescription(
        key="silence_alarm",
        name="Silence Alarm",
        press_fn="silence_alarm",
        entity_registry_enabled_default=True,
    ),
    ZControlButtonEntityDescription(
        key="reset_device",
        name="Reset Device",
        press_fn="reset_device",
        entity_registry_enabled_default=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ZControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Z-Control buttons from a config entry."""
    coordinator = entry.runtime_data.coordinator
    client = entry.runtime_data.client

    def create_entities(device_id: str, device: dict[str, Any]) -> list[ZControlButton]:
        return [
            ZControlButton(
                coordinator=coordinator,
                client=client,
                device_id=device_id,
                device=device,
                description=description,
            )
            for description in BUTTON_DESCRIPTIONS
        ]

    async_setup_entities(entry, async_add_entities, create_entities)


class ZControlButton(CoordinatorEntity[ZControlCoordinator], ButtonEntity):
    """Representation of a Z-Control button."""

    _attr_has_entity_name = True
    entity_description: ZControlButtonEntityDescription

    def __init__(
        self,
        coordinator: ZControlCoordinator,
        client: ZControlApiClient,
        device_id: str,
        device: dict[str, Any],
        description: ZControlButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._device_id = device_id
        self._client = client
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

    async def async_press(self) -> None:
        """Handle button press."""
        # Get the method from the client
        method = getattr(self._client, self.entity_description.press_fn)

        # Call the method with device ID
        success = await method(self._device_id)

        if success:
            _LOGGER.debug(
                "Successfully sent %s command to device %s",
                self.entity_description.key,
                self._device_id,
            )
            # Refresh data after command
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.warning(
                "Failed to send %s command to device %s",
                self.entity_description.key,
                self._device_id,
            )
