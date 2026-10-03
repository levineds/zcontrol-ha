"""Run real Home Assistant platform setup and unload with a simulated cloud."""

import json
from pathlib import Path
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest

from custom_components.zcontrol.const import DOMAIN


@pytest.mark.asyncio
async def test_setup_discovery_options_reload_and_unload(hass, make_config_entry):
    loader.async_setup(hass)
    if hasattr(dr, "async_setup"):
        dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    integration_path = (
        Path(__file__).resolve().parents[1] / "custom_components" / DOMAIN
    )
    manifest = json.loads((integration_path / "manifest.json").read_text())
    hass.data[loader.DATA_INTEGRATIONS][DOMAIN] = loader.Integration(
        hass,
        f"custom_components.{DOMAIN}",
        integration_path,
        manifest,
        top_level_files={path.name for path in integration_path.iterdir()},
    )
    hass.config_entries = ConfigEntries(hass, {})
    device = {
        "deviceID": "test-first",
        "deviceName": "First sump",
        "family": "APAK_SENTRY",
        "deviceOnline": 1,
        "alarmCount": 0,
        "lastHeartbeat": "2026-10-03T12:34:56Z",
        "deviceStatusList": [
            {"statusName": name, "isFault": 0, "alarmActiveValue": 0}
            for name in ["Input 1", "Input 2", "AC Power", "Battery"]
        ],
    }
    client = MagicMock(
        authenticate=AsyncMock(),
        get_devices=AsyncMock(return_value=[{"devices": [device]}]),
    )
    entry = make_config_entry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test account",
        data={"email": "test@example.invalid", "password": "synthetic-password"},
        options={},
        source="user",
        unique_id="test@example.invalid",
        discovery_keys=MappingProxyType({}),
    )
    with patch("custom_components.zcontrol.ZControlApiClient", return_value=client):
        await hass.config_entries.async_add(entry)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        first_session = entry.runtime_data.session
        registry = er.async_get(hass)
        initial = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(initial) == 11
        assert hass.states.get("sensor.first_sump_alarm_count").state == "0"
        assert hass.states.get("binary_sensor.first_sump_input_1").state == "off"
        assert (
            hass.states.get("sensor.first_sump_last_heartbeat").state
            == "2026-10-03T12:34:56+00:00"
        )
        client.get_devices.return_value = [
            {
                "devices": [
                    device,
                    {**device, "deviceID": "test-second", "deviceName": "Second sump"},
                ]
            }
        ]
        await entry.runtime_data.coordinator.async_request_refresh()
        await hass.async_block_till_done()
        assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 22
        hass.config_entries.async_update_entry(
            entry, options={"account_time_zone": "Europe/London"}
        )
        await hass.async_block_till_done()
        assert first_session.closed
        assert entry.runtime_data.coordinator.account_time_zone.key == "Europe/London"
        assert len(er.async_entries_for_config_entry(registry, entry.entry_id)) == 22
        session = entry.runtime_data.session
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
        assert session.closed
        assert entry.state is ConfigEntryState.NOT_LOADED
