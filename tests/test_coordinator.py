"""Distinguish transient outages from actual authentication failures."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest

from custom_components.zcontrol.api import ZControlApiError, ZControlAuthError
from custom_components.zcontrol.coordinator import ZControlCoordinator


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "stage,error,expected",
    [
        ("initial", ZControlApiError("temporary outage"), UpdateFailed),
        ("initial", TimeoutError(), UpdateFailed),
        ("login", ZControlApiError("temporary outage"), UpdateFailed),
        ("login", TimeoutError(), UpdateFailed),
        ("retry", ZControlApiError("temporary outage"), UpdateFailed),
        ("retry", TimeoutError(), UpdateFailed),
        ("login", ZControlAuthError("invalid authentication"), ConfigEntryAuthFailed),
        ("retry", ZControlAuthError("invalid authentication"), ConfigEntryAuthFailed),
    ],
)
async def test_update_failure_classification(stage, error, expected):
    coordinator = MagicMock(spec=ZControlCoordinator)
    coordinator.client = MagicMock(authenticate=AsyncMock())
    if stage == "initial":
        coordinator._fetch_devices = AsyncMock(side_effect=error)
    else:
        coordinator._fetch_devices = AsyncMock(
            side_effect=[ZControlAuthError("expired"), error]
        )
        if stage == "login":
            coordinator.client.authenticate.side_effect = error
    with pytest.raises(expected):
        await ZControlCoordinator._async_update_data(coordinator)
    if stage == "initial":
        coordinator.client.authenticate.assert_not_awaited()
    else:
        coordinator.client.authenticate.assert_awaited_once()


@pytest.mark.asyncio
async def test_expired_token_reauthenticates_and_retries_once():
    coordinator = MagicMock(spec=ZControlCoordinator)
    coordinator.client = MagicMock(authenticate=AsyncMock())
    devices = {"locations": [], "devices": {}}
    coordinator._fetch_devices = AsyncMock(
        side_effect=[ZControlAuthError("expired"), devices]
    )
    assert await ZControlCoordinator._async_update_data(coordinator) is devices
    assert coordinator._fetch_devices.await_count == 2
    coordinator.client.authenticate.assert_awaited_once()
