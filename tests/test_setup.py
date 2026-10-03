"""Verify session lifetime on setup, retries, cancellation, and unload."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
import pytest

from custom_components import zcontrol
from custom_components.zcontrol.api import ZControlApiError, ZControlAuthError


@pytest.fixture
def setup_dependencies():
    session = MagicMock(close=AsyncMock())
    client = MagicMock(authenticate=AsyncMock())
    coordinator = MagicMock(async_config_entry_first_refresh=AsyncMock())
    coordinator.account_time_zone = SimpleNamespace(key="UTC")
    entry = MagicMock(
        data={"email": "test@example.invalid", "password": "synthetic-password"},
        options={},
    )
    hass = SimpleNamespace(
        config=SimpleNamespace(time_zone="UTC"),
        config_entries=SimpleNamespace(
            async_forward_entry_setups=AsyncMock(),
            async_unload_platforms=AsyncMock(return_value=True),
            async_reload=AsyncMock(),
        ),
    )
    with (
        patch.object(zcontrol.aiohttp, "ClientSession", return_value=session),
        patch.object(zcontrol, "ZControlApiClient", return_value=client),
        patch.object(zcontrol, "ZControlCoordinator", return_value=coordinator),
    ):
        yield hass, entry, session, client, coordinator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage,error,expected",
    [
        ("login", ZControlAuthError("invalid authentication"), ConfigEntryAuthFailed),
        ("login", ZControlApiError("network unavailable"), ConfigEntryNotReady),
        ("refresh", ConfigEntryNotReady("retry"), ConfigEntryNotReady),
        ("platform", RuntimeError("platform failure"), RuntimeError),
        ("refresh", asyncio.CancelledError(), asyncio.CancelledError),
    ],
)
async def test_failed_setup_closes_session(setup_dependencies, stage, error, expected):
    hass, entry, session, client, coordinator = setup_dependencies
    methods = {
        "login": client.authenticate,
        "refresh": coordinator.async_config_entry_first_refresh,
        "platform": hass.config_entries.async_forward_entry_setups,
    }
    methods[stage].side_effect = error
    with pytest.raises(expected):
        await zcontrol.async_setup_entry(hass, entry)
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_setup_keeps_session_until_unload(setup_dependencies):
    hass, entry, session, client, coordinator = setup_dependencies
    assert await zcontrol.async_setup_entry(hass, entry)
    assert entry.runtime_data.session is session
    assert entry.runtime_data.coordinator is coordinator
    client.authenticate.assert_awaited_once()
    coordinator.async_config_entry_first_refresh.assert_awaited_once()
    entry.add_update_listener.assert_called_once_with(zcontrol.async_reload_entry)
    session.close.assert_not_awaited()
    assert await zcontrol.async_unload_entry(hass, entry)
    session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_unload_keeps_session_for_loaded_entities(setup_dependencies):
    hass, entry, session, _, _ = setup_dependencies
    await zcontrol.async_setup_entry(hass, entry)
    hass.config_entries.async_unload_platforms.return_value = False
    assert not await zcontrol.async_unload_entry(hass, entry)
    session.close.assert_not_awaited()


@pytest.mark.asyncio
async def test_option_update_reloads_entry(setup_dependencies):
    hass, entry, _, _, _ = setup_dependencies
    await zcontrol.async_setup_entry(hass, entry)
    entry.options = {"account_time_zone": "Europe/London"}
    await zcontrol.async_reload_entry(hass, entry)
    hass.config_entries.async_reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.asyncio
async def test_unchanged_timezone_does_not_duplicate_reauth_reload(setup_dependencies):
    hass, entry, _, _, _ = setup_dependencies
    await zcontrol.async_setup_entry(hass, entry)
    await zcontrol.async_reload_entry(hass, entry)
    hass.config_entries.async_reload.assert_not_awaited()
