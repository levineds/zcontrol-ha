"""Discover new devices without duplicating or deleting existing entities."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
import pytest

from custom_components.zcontrol import binary_sensor, button, sensor
from custom_components.zcontrol.coordinator import ZControlCoordinator
from custom_components.zcontrol.entity import async_setup_entities


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "platform,count", [(binary_sensor, 5), (sensor, 4), (button, 2)]
)
async def test_platform_discovery_and_cleanup(hass, platform, count):
    coordinator = ZControlCoordinator(hass, MagicMock())
    coordinator.data = {"devices": {"test-first": {"deviceName": "First"}}}
    entry = MagicMock(
        runtime_data=SimpleNamespace(coordinator=coordinator, client=MagicMock())
    )
    entities = []
    await platform.async_setup_entry(hass, entry, entities.extend)
    assert len(entities) == count
    original_ids = {entity.unique_id for entity in entities}
    coordinator.async_set_updated_data(
        {
            "devices": {
                "test-first": {"deviceName": "First"},
                "test-second": {"deviceName": "Second"},
            }
        }
    )
    assert len(entities) == 2 * count
    assert len({entity.unique_id for entity in entities}) == 2 * count
    coordinator.async_set_updated_data({"devices": {"test-second": {}}})
    assert len(entities) == 2 * count
    assert all(not entity.available for entity in entities[:count])
    coordinator.async_set_updated_data(
        {"devices": {"test-first": {}, "test-second": {}}}
    )
    assert len(entities) == 2 * count
    assert all(entity.available for entity in entities)
    assert original_ids.issubset({entity.unique_id for entity in entities})
    entry.async_on_unload.call_args.args[0]()
    coordinator.async_set_updated_data({"devices": {"test-third": {}}})
    assert len(entities) == 2 * count
    await hass.async_block_till_done()


@pytest.mark.asyncio
async def test_supported_status_appearing_later(hass):
    """The helper also discovers newly available entities on an existing device."""
    coordinator = ZControlCoordinator(hass, MagicMock())
    coordinator.data = {"devices": {"test-device": {"statuses": ["first"]}}}
    entry = MagicMock(runtime_data=SimpleNamespace(coordinator=coordinator))
    entities = []

    @callback
    def create_entities(device_id, device):
        for status in device["statuses"]:
            entity = Entity()
            entity._attr_unique_id = f"{device_id}_{status}"
            yield entity

    async_setup_entities(entry, entities.extend, create_entities)
    assert [entity.unique_id for entity in entities] == ["test-device_first"]
    coordinator.async_set_updated_data(
        {"devices": {"test-device": {"statuses": ["first", "second"]}}}
    )
    assert [entity.unique_id for entity in entities] == [
        "test-device_first",
        "test-device_second",
    ]
    coordinator.async_set_update_error(RuntimeError("offline"))
    assert len(entities) == 2
    coordinator.async_set_updated_data(
        {"devices": {"test-device": {"statuses": ["first", "second"]}}}
    )
    assert len(entities) == 2
    entry.async_on_unload.call_args.args[0]()
    await hass.async_block_till_done()
