"""Exercise setup, reauthentication, and timezone options on the supported minimum."""

from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import data_entry_flow
from homeassistant.config_entries import ConfigEntries
import pytest

from custom_components.zcontrol.api import ZControlApiError, ZControlAuthError
from custom_components.zcontrol.config_flow import (
    ZControlConfigFlow,
    ZControlOptionsFlow,
)
from custom_components.zcontrol.const import CONF_ACCOUNT_TIME_ZONE, DOMAIN


@pytest.fixture
def entry(hass, make_config_entry):
    hass.config_entries = ConfigEntries(hass, {})
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
    hass.config_entries._entries[entry.entry_id] = entry
    return entry


def config_flow(hass, source="user", entry_id=None):
    flow = ZControlConfigFlow()
    flow.hass = hass
    flow.handler = DOMAIN
    flow.flow_id = "test-flow"
    flow.context = {"source": source}
    if entry_id:
        flow.context["entry_id"] = entry_id
    return flow


@pytest.mark.asyncio
async def test_user_flow_creates_entry_after_validation(hass):
    hass.config_entries = ConfigEntries(hass, {})
    flow = config_flow(hass)
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    client = MagicMock(authenticate=AsyncMock())
    data = {"email": "test@example.invalid", "password": "synthetic-password"}
    with patch(
        "custom_components.zcontrol.config_flow.ZControlApiClient", return_value=client
    ):
        result = await flow.async_step_user(data)
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == data
    assert flow.unique_id == "test@example.invalid"
    client.authenticate.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,expected",
    [
        (ZControlAuthError("invalid authentication"), "invalid_auth"),
        (ZControlApiError("temporary outage"), "cannot_connect"),
    ],
)
async def test_reauth_failure_retains_existing_entry(hass, entry, error, expected):
    flow = config_flow(hass, "reauth", entry.entry_id)
    result = await flow.async_step_reauth(dict(entry.data))
    assert result["step_id"] == "reauth_confirm"
    client = MagicMock(authenticate=AsyncMock(side_effect=error))
    with patch(
        "custom_components.zcontrol.config_flow.ZControlApiClient", return_value=client
    ):
        result = await flow.async_step_reauth_confirm(
            {"password": "synthetic-replacement"}
        )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": expected}
    assert entry.data["password"] == "synthetic-password"


@pytest.mark.asyncio
async def test_reauth_updates_existing_entry_and_reloads(hass, entry):
    flow = config_flow(hass, "reauth", entry.entry_id)
    client = MagicMock(authenticate=AsyncMock())
    with (
        patch(
            "custom_components.zcontrol.config_flow.ZControlApiClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
    ):
        result = await flow.async_step_reauth_confirm(
            {"password": "synthetic-replacement"}
        )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "synthetic-replacement"
    assert entry.unique_id == "test@example.invalid"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    reload.assert_called_once_with(entry.entry_id)


@pytest.mark.asyncio
async def test_timezone_options_validation_and_default(hass, entry):
    await hass.config.async_set_time_zone("America/Chicago")
    flow = ZControlConfigFlow.async_get_options_flow(entry)
    assert isinstance(flow, ZControlOptionsFlow)
    flow.hass = hass
    flow.handler = entry.entry_id
    flow.flow_id = "test-options"
    result = await flow.async_step_init()
    assert result["data_schema"]({})[CONF_ACCOUNT_TIME_ZONE] == "America/Chicago"
    result = await flow.async_step_init({CONF_ACCOUNT_TIME_ZONE: "invalid/timezone"})
    assert result["errors"] == {CONF_ACCOUNT_TIME_ZONE: "invalid_time_zone"}
    result = await flow.async_step_init({CONF_ACCOUNT_TIME_ZONE: "Europe/London"})
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ACCOUNT_TIME_ZONE: "Europe/London"}
