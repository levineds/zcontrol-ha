"""The Z-Control Sump Pump Alarm integration."""

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import ZControlApiClient, ZControlAuthError, ZControlApiError
from .const import CONF_ACCOUNT_TIME_ZONE, DOMAIN
from .coordinator import ZControlCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]

type ZControlConfigEntry = ConfigEntry[ZControlData]


class ZControlData:
    """Runtime data for Z-Control integration."""

    def __init__(
        self,
        coordinator: ZControlCoordinator,
        client: ZControlApiClient,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize runtime data."""
        self.coordinator = coordinator
        self.client = client
        self.session = session


async def async_setup_entry(hass: HomeAssistant, entry: ZControlConfigEntry) -> bool:
    """Set up Z-Control from a config entry."""
    # Create session and client
    session = aiohttp.ClientSession()

    setup_complete = False
    try:
        client = ZControlApiClient(
            session,
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
        )
        # Authenticate
        await client.authenticate()

        coordinator = ZControlCoordinator(
            hass, client, entry.options.get(CONF_ACCOUNT_TIME_ZONE)
        )
        await coordinator.async_config_entry_first_refresh()

        entry.runtime_data = ZControlData(coordinator, client, session)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        entry.async_on_unload(entry.add_update_listener(async_reload_entry))
        setup_complete = True
    except ZControlAuthError as err:
        raise ConfigEntryAuthFailed("Authentication failed") from err
    except ZControlApiError as err:
        raise ConfigEntryNotReady(f"Connection failed: {err}") from err
    finally:
        # Includes first-refresh/platform failures and cancelled setup attempts.
        if not setup_complete:
            await session.close()

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ZControlConfigEntry) -> None:
    """Apply updated options by reloading the entry."""
    time_zone = entry.options.get(CONF_ACCOUNT_TIME_ZONE, hass.config.time_zone)
    if time_zone != entry.runtime_data.coordinator.account_time_zone.key:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ZControlConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Close the session
        await entry.runtime_data.session.close()

    return unload_ok
