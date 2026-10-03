"""Synthetic portal detail payloads, with no real account/device identifiers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.zcontrol.api import ZControlApiError, ZControlAuthError
from custom_components.zcontrol.coordinator import ZControlCoordinator
from custom_components.zcontrol.sensor import (
    DETAIL_SENSOR_DESCRIPTIONS,
    async_setup_entry,
    parse_detail_value,
)
from tests.test_binary_sensor import coordinator, device, setup


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "asserted,expected", [(1, False), (0, True), (None, None), ("1", None), (2, None)]
)
async def test_ac_power_on_polarity(asserted, expected):
    result, entities = await setup(
        {"test-508": device(["System Ready", "DC Pump", "Float Status"])}
    )
    result.get_device("test-508")["statusDetails"] = [
        {"statusName": "AC Power On", "assertedValue": asserted, "isFault": 0},
    ]
    assert entities["test-508_ac_power"].is_on is expected
    # Readiness faults and alarm silencing must not change mains detection.
    result.get_device_status("test-508", "System Ready")["isFault"] = 1
    assert entities["test-508_ac_power"].is_on is expected
    result.get_device("test-508")["deviceStatusList"].append(
        {"statusName": "AC Power", "isFault": 0, "alarmActiveValue": 0}
    )
    assert entities["test-508_ac_power"].is_on is False


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        ("12.76 V", "V", 12.76),
        ("-1.2 A", "A", -1.2),
        ("0 A", "A", 0),
        ("4", "", 4),
        ("1 Min", "duration", 1),
        ("13 Hours, 40 Mins", "duration", 820),
        ("1 Day, 2 Hours, 3 Mins", "duration", 1563),
        ("30 Secs", "duration", 0.5),
        ("2 Minutes", "duration", 2),
        ("30 Seconds", "duration", 0.5),
        ("0 Mins", "duration", 0),
        ("unknown", "V", None),
        ("12.7 mV", "V", None),
        ("1 Hour junk", "duration", None),
        ("", "duration", None),
        (None, "V", None),
        ("-1", "", None),
        ("1.5", "", None),
    ],
)
def test_detail_units(value, unit, expected):
    assert parse_detail_value(value, unit) == expected


@pytest.mark.asyncio
async def test_sensor_discovery_and_refresh():
    payload = device(["System Ready", "DC Pump", "Float Status"])
    payload["sensorDetails"] = [
        {"description": "Battery Voltage", "value": "12.76 V"},
        {"description": "High Water Float Count", "value": "4"},
        {"description": "Pump Runtime", "value": "1 Min"},
    ]
    result = coordinator({"test-508": payload, "test-apak": device(["Input 1"])})
    entry = MagicMock(runtime_data=SimpleNamespace(coordinator=result))
    entities = []
    await async_setup_entry(None, entry, entities.extend)
    values = {entity.unique_id: entity for entity in entities}
    assert values["test-508_battery_voltage"].native_value == 12.76
    assert values["test-508_high_water_float_count"].native_value == 4
    assert values["test-508_pump_runtime"].native_value == 1
    assert "test-apak_battery_voltage" not in values
    assert "test-508_battery_current" not in values
    result.get_device("test-508")["sensorDetails"] = []
    assert values["test-508_battery_voltage"].native_value is None
    result.get_device("test-508")["sensorDetails"] = [
        {"description": "Battery Voltage", "value": "12.9 V"}
    ]
    assert values["test-508_battery_voltage"].native_value == 12.9


@pytest.mark.asyncio
async def test_only_508_capabilities_fetch_optional_details(hass):
    main = device(["System Ready", "Battery", "DC Pump", "Float Status"])
    main["deviceID"] = "test-508"
    apak = device(["Input 1", "Input 2", "AC Power", "Battery"])
    apak["deviceID"] = "test-apak"
    detail = {
        "deviceID": "test-508",
        "deviceStatusList": [{"statusName": "AC Power On", "assertedValue": 1}],
    }
    client = MagicMock(
        get_devices=AsyncMock(
            side_effect=[[{"devices": [main, apak]}], [{"devices": [detail]}]]
        ),
        get_device_status=AsyncMock(
            return_value=[{"description": "Battery Voltage", "value": "12.76 V"}]
        ),
    )
    result = ZControlCoordinator(hass, client)
    data = await result._fetch_devices()
    result.async_set_updated_data(data)
    assert result.get_device_status("test-508", "AC Power On")["assertedValue"] == 1
    assert "sensorDetails" not in data["devices"]["test-apak"]
    assert client.get_devices.await_args_list[1].args == ("test-508",)
    client.get_device_status.assert_awaited_once_with("test-508")


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [ZControlApiError("unavailable"), TimeoutError()])
async def test_optional_failure_clears_readings_without_losing_overview(hass, error):
    client = MagicMock(
        get_devices=AsyncMock(side_effect=error),
        get_device_status=AsyncMock(side_effect=error),
    )
    result = ZControlCoordinator(hass, client)
    payload = {"sensorDetails": [{"description": "Battery Voltage", "value": "12 V"}]}
    await result._fetch_device_details("test-508", payload)
    assert payload == {"statusDetails": [], "sensorDetails": []}


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["status", "sensor"])
async def test_optional_auth_errors_propagate(hass, stage):
    client = MagicMock(
        get_devices=AsyncMock(return_value=[]),
        get_device_status=AsyncMock(return_value=[]),
    )
    method = client.get_devices if stage == "status" else client.get_device_status
    method.side_effect = ZControlAuthError("expired")
    with pytest.raises(ZControlAuthError):
        await ZControlCoordinator(hass, client)._fetch_device_details("test-508", {})


@pytest.mark.asyncio
async def test_malformed_optional_lists(hass):
    client = MagicMock(
        get_devices=AsyncMock(return_value={}),
        get_device_status=AsyncMock(return_value={}),
    )
    payload = {}
    await ZControlCoordinator(hass, client)._fetch_device_details("test-508", payload)
    assert payload == {"statusDetails": [], "sensorDetails": []}


def test_long_runtime_display_units():
    from homeassistant.const import UnitOfTime

    descriptions = {
        description.key: description for description in DETAIL_SENSOR_DESCRIPTIONS
    }
    for key in ("system_run_time", "up_time"):
        assert descriptions[key].native_unit_of_measurement == UnitOfTime.MINUTES
        assert descriptions[key].suggested_unit_of_measurement == UnitOfTime.DAYS
    assert descriptions["pump_runtime"].suggested_unit_of_measurement is None
