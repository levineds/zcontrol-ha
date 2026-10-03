"""Regression tests for status discovery and existing device behavior.

Payloads are synthetic examples of the fields used by the integration, not
captured cloud responses. No account credentials or device identifiers are used.
"""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.zcontrol.binary_sensor import async_setup_entry
from custom_components.zcontrol.coordinator import ZControlCoordinator


def device(status_names, family="APAK_SENTRY"):
    """Build a synthetic cloud device with healthy status entries."""
    return {
        "deviceName": "Test sump",
        "family": family,
        "deviceOnline": 1,
        "deviceStatusList": [
            {"statusName": name, "isFault": 0, "alarmActiveValue": 0}
            for name in status_names
        ],
    }


def coordinator(devices):
    """Use real lookup methods without making network requests."""
    result = MagicMock(spec=ZControlCoordinator)
    result.data = {"devices": deepcopy(devices)}
    result.last_update_success = True
    result.get_device.side_effect = lambda device_id: ZControlCoordinator.get_device(
        result, device_id
    )
    result.get_device_status.side_effect = (
        lambda device_id, name: ZControlCoordinator.get_device_status(
            result, device_id, name
        )
    )
    return result


async def setup(devices):
    """Collect entities from the actual platform setup."""
    result = coordinator(devices)
    entry = SimpleNamespace(runtime_data=SimpleNamespace(coordinator=result))
    entities = []
    await async_setup_entry(None, entry, entities.extend)
    return result, {entity.unique_id: entity for entity in entities}


@pytest.mark.asyncio
async def test_508_statuses_and_legacy_ids():
    """Expose 508 status names even when family is a numeric API identifier."""
    result, entities = await setup(
        {
            "test-508": device(
                ["System Ready", "Battery", "DC Pump", "Float Status"], 107
            )
        }
    )
    assert set(entities) == {
        "test-508_online",
        "test-508_input_1",
        "test-508_input_2",
        "test-508_ac_power",
        "test-508_battery",
        "test-508_system_ready",
        "test-508_dc_pump",
        "test-508_float_status",
    }
    for key in ("battery", "system_ready", "dc_pump", "float_status"):
        assert entities[f"test-508_{key}"].is_on is False
    for key in ("input_1", "input_2", "ac_power"):
        assert entities[f"test-508_{key}"].is_on is None
    result.get_device_status("test-508", "DC Pump")["isFault"] = 1
    assert entities["test-508_dc_pump"].is_on is True
    assert entities["test-508_battery"].is_on is False


@pytest.mark.asyncio
@pytest.mark.parametrize("family", ["APAK_SENTRY", "another-model", 42, None])
async def test_non_508_entities_unchanged(family):
    """Other devices retain the five existing unique IDs and their semantics."""
    result, entities = await setup(
        {"test-other": device(["Input 1", "Input 2", "AC Power", "Battery"], family)}
    )
    assert set(entities) == {
        "test-other_online",
        "test-other_input_1",
        "test-other_input_2",
        "test-other_ac_power",
        "test-other_battery",
    }
    assert entities["test-other_online"].is_on is True
    for key, name in (
        ("input_1", "Input 1"),
        ("input_2", "Input 2"),
        ("ac_power", "AC Power"),
        ("battery", "Battery"),
    ):
        sensor = entities[f"test-other_{key}"]
        status = result.get_device_status("test-other", name)
        assert sensor.is_on is False
        status["isFault"] = 1
        assert sensor.is_on is True
        status["isFault"] = 0
        status["alarmActiveValue"] = 1
        assert sensor.is_on is True
        status["alarmActiveValue"] = 0
        assert sensor.is_on is False
    result.get_device("test-other")["deviceOnline"] = 0
    assert entities["test-other_online"].is_on is False


@pytest.mark.asyncio
async def test_mixed_account_and_missing_statuses():
    """Add only reported statuses and isolate entities across devices."""
    result, entities = await setup(
        {
            "test-508": device(["System Ready", "Battery", "DC Pump", "Float Status"]),
            "test-apak": device(["Input 1", "Input 2", "AC Power", "Battery"]),
            "test-partial": device(["Battery", "DC Pump"]),
            "test-empty": device([]),
        }
    )
    assert "test-apak_dc_pump" not in entities
    assert "test-partial_dc_pump" in entities
    assert "test-partial_system_ready" not in entities
    assert "test-empty_dc_pump" not in entities
    assert entities["test-empty_battery"].is_on is None
    result.get_device_status("test-508", "Battery")["alarmActiveValue"] = 1
    assert entities["test-508_battery"].is_on is True
    assert entities["test-apak_battery"].is_on is False
    result.get_device("test-508")["deviceStatusList"] = []
    assert entities["test-508_dc_pump"].is_on is None
    result.last_update_success = False
    assert entities["test-apak_online"].available is False
    result.last_update_success = True
    result.data["devices"].pop("test-508")
    assert entities["test-508_dc_pump"].available is False
    assert entities["test-508_dc_pump"].is_on is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status_name, key",
    [
        ("System Ready", "system_ready"),
        ("DC Pump", "dc_pump"),
        ("Float Status", "float_status"),
    ],
)
async def test_additional_faults_follow_updated_coordinator_data(status_name, key):
    """New statuses use the same fault rule and refresh path as legacy sensors."""
    result, entities = await setup({"test-device": device([status_name])})
    sensor = entities[f"test-device_{key}"]
    assert sensor.is_on is False
    updated = device([status_name])
    updated["deviceStatusList"][0]["alarmActiveValue"] = 1
    result.data["devices"]["test-device"] = updated
    assert sensor.is_on is True
    updated["deviceStatusList"][0]["alarmActiveValue"] = 0
    updated["deviceStatusList"][0]["isFault"] = 1
    assert sensor.is_on is True
    updated["deviceStatusList"][0]["isFault"] = 0
    assert sensor.is_on is False
