"""Data update coordinator for Z-Control integration."""

import logging
from datetime import timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ZControlApiClient, ZControlAuthError, ZControlApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ZControlCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Z-Control data updates."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: ZControlApiClient,
        account_time_zone: str | None = None,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.account_time_zone = ZoneInfo(account_time_zone or hass.config.time_zone)

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the API.

        Returns a dictionary with:
        - locations: List of locations with devices
        - devices: Flattened dict of device_id -> device data for easy lookup
        """
        try:
            return await self._fetch_devices()

        except ZControlAuthError:
            # Token expired - try to re-authenticate automatically
            _LOGGER.debug("Auth token expired, attempting to re-authenticate")
            try:
                await self.client.authenticate()
                _LOGGER.info("Successfully re-authenticated with Z-Control")
                # Retry the API call with the new token
                return await self._fetch_devices()
            except ZControlAuthError as reauth_err:
                # Re-authentication failed - credentials may have changed
                _LOGGER.warning("Re-authentication failed: %s", reauth_err)
                raise ConfigEntryAuthFailed(
                    "Failed to re-authenticate. Please update your credentials."
                ) from reauth_err
            except (ZControlApiError, TimeoutError) as err:
                # An outage during login or the retry does not invalidate credentials.
                raise UpdateFailed(str(err)) from err

        except (ZControlApiError, TimeoutError) as err:
            # This will retry at the next interval
            raise UpdateFailed(str(err)) from err
        except Exception as err:
            _LOGGER.exception("Unexpected error fetching Z-Control data")
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _fetch_devices(self) -> dict[str, Any]:
        """Fetch and process device data from the API."""
        locations = await self.client.get_devices()

        # Build a flattened device lookup for easy access
        devices: dict[str, dict[str, Any]] = {}
        for location in locations:
            location_name = location.get("locationName", "Unknown")
            for device in location.get("devices", []):
                device_id = device.get("deviceID")
                if device_id:
                    # Add location info to device
                    device["locationName"] = location_name
                    device["locationID"] = location.get("locationID")
                    device["locationHasFault"] = location.get("locationHasFault", False)
                    devices[device_id] = device

        return {
            "locations": locations,
            "devices": devices,
        }

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        """Get device data by ID."""
        if self.data is None:
            return None
        return self.data.get("devices", {}).get(device_id)

    def get_device_status(self, device_id: str, status_name: str) -> dict[str, Any] | None:
        """Get a specific status entry from a device's statusList.

        Args:
            device_id: The device ID
            status_name: The status name (e.g., "Input 1", "AC Power")

        Returns the status entry dict or None if not found.
        """
        device = self.get_device(device_id)
        if device is None:
            return None

        status_list = device.get("deviceStatusList", [])
        for status in status_list:
            if status.get("statusName") == status_name:
                return status
        return None
