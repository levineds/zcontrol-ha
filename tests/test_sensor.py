"""Test missing alarm counts and timezone-aware heartbeat readings."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from custom_components.zcontrol.coordinator import ZControlCoordinator
from custom_components.zcontrol.sensor import SENSOR_DESCRIPTIONS, ZControlSensor


def sensor(key, data, time_zone="America/Chicago"):
    coordinator = MagicMock(spec=ZControlCoordinator)
    coordinator.get_device.return_value = data
    coordinator.account_time_zone = ZoneInfo(time_zone)
    coordinator.last_update_success = True
    description = next(
        description for description in SENSOR_DESCRIPTIONS if description.key == key
    )
    return ZControlSensor(coordinator, "test-device", {}, description)


@pytest.mark.parametrize(
    "data,expected",
    [
        ({}, None),
        ({"alarmCount": None}, None),
        ({"alarmCount": 0}, 0),
        ({"alarmCount": 3}, 3),
    ],
)
def test_alarm_count(data, expected):
    assert sensor("alarm_count", data).native_value == expected


@pytest.mark.parametrize(
    "timestamp,offset",
    [
        ("2026-10-03T12:34:56Z", 0),
        ("2026-10-03T12:34:56.123456+00:00", 0),
        ("2026-10-03T12:34:56+02:00", 2),
        ("2026-10-03T12:34:56-07:00", -7),
    ],
)
def test_explicit_offsets_preserved(timestamp, offset):
    value = sensor("last_heartbeat", {"lastHeartbeat": timestamp}).native_value
    assert value.hour == 12 and value.minute == 34
    assert value.utcoffset() == timedelta(hours=offset)
    assert value == datetime.fromisoformat(timestamp)


@pytest.mark.parametrize(
    "timestamp",
    [
        "10-03-2026 12:34:56 PM",
        "2026-10-03T12:34:56",
        "2026-10-03T12:34:56.123456",
    ],
)
@pytest.mark.parametrize(
    "time_zone,offset", [("America/Chicago", -5), ("Europe/London", 1)]
)
def test_naive_timestamps_use_account_timezone(timestamp, time_zone, offset):
    value = sensor(
        "last_heartbeat", {"lastHeartbeat": timestamp}, time_zone
    ).native_value
    assert value.hour == 12 and value.minute == 34
    assert value.utcoffset() == timedelta(hours=offset)


@pytest.mark.parametrize("timestamp", [None, "", "not a timestamp", 123])
def test_invalid_heartbeats_are_unknown(timestamp):
    assert sensor("last_heartbeat", {"lastHeartbeat": timestamp}).native_value is None


def test_missing_device_unavailable():
    entity = sensor("alarm_count", None)
    assert entity.native_value is None
    assert entity.available is False


@pytest.mark.asyncio
async def test_default_account_timezone(hass):
    await hass.config.async_set_time_zone("America/Chicago")
    coordinator = ZControlCoordinator(hass, MagicMock())
    assert coordinator.account_time_zone.key == "America/Chicago"
    override = ZControlCoordinator(hass, MagicMock(), "Europe/London")
    assert override.account_time_zone.key == "Europe/London"
