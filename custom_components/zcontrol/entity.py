"""Discover platform entities as the cloud device list changes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

if TYPE_CHECKING:
    from . import ZControlConfigEntry


@callback
def async_setup_entities(
    entry: ZControlConfigEntry,
    async_add_entities: AddEntitiesCallback,
    create_entities: Callable[[str, dict[str, Any]], Iterable[Entity]],
) -> None:
    """Add each unique entity once and stop discovery when the entry unloads."""
    coordinator = entry.runtime_data.coordinator
    known_entities: set[str] = set()

    @callback
    def async_discover_entities() -> None:
        if not coordinator.last_update_success or not coordinator.data:
            return
        entities: list[Entity] = []
        for device_id, device in coordinator.data.get("devices", {}).items():
            for entity in create_entities(device_id, device):
                unique_id = entity.unique_id
                if unique_id is None or unique_id in known_entities:
                    continue
                known_entities.add(unique_id)
                entities.append(entity)
        if entities:
            async_add_entities(entities)

    async_discover_entities()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_entities))
