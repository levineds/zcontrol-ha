"""Config flow for Z-Control integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .api import ZControlApiClient, ZControlAuthError, ZControlApiError
from .const import CONF_ACCOUNT_TIME_ZONE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ZControlConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Z-Control."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ZControlOptionsFlow:
        """Return the options flow for this entry."""
        return ZControlOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured with this email
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()

            # Validate credentials
            try:
                async with aiohttp.ClientSession() as session:
                    client = ZControlApiClient(
                        session,
                        user_input[CONF_EMAIL],
                        user_input[CONF_PASSWORD],
                    )
                    await client.authenticate()

                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data=user_input,
                )

            except ZControlAuthError:
                errors["base"] = "invalid_auth"
            except ZControlApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during config flow")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization when token expires."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauth confirmation."""
        errors: dict[str, str] = {}

        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                async with aiohttp.ClientSession() as session:
                    client = ZControlApiClient(
                        session,
                        reauth_entry.data[CONF_EMAIL],
                        user_input[CONF_PASSWORD],
                    )
                    await client.authenticate()

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_EMAIL: reauth_entry.data[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

            except ZControlAuthError:
                errors["base"] = "invalid_auth"
            except ZControlApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
            description_placeholders={
                CONF_EMAIL: reauth_entry.data[CONF_EMAIL],
            },
        )


class ZControlOptionsFlow(OptionsFlow):
    """Configure interpretation of timestamps without an explicit offset."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the Z-Control account timezone."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                time_zone = cv.time_zone(user_input[CONF_ACCOUNT_TIME_ZONE])
            except vol.Invalid:
                errors[CONF_ACCOUNT_TIME_ZONE] = "invalid_time_zone"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        **self._config_entry.options,
                        CONF_ACCOUNT_TIME_ZONE: time_zone,
                    },
                )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ACCOUNT_TIME_ZONE,
                        default=self._config_entry.options.get(
                            CONF_ACCOUNT_TIME_ZONE, self.hass.config.time_zone
                        ),
                    ): str,
                }
            ),
            errors=errors,
        )
