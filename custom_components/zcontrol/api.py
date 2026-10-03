"""API client for Z-Control cloud service."""

import logging
import re
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    AUTH_TOKEN_COOKIE,
    COMMAND_ALARM_SILENCE,
    COMMAND_DEVICE_RESET,
    LOGIN_URL,
    SUBSCRIPTION_KEY,
)

_LOGGER = logging.getLogger(__name__)


class ZControlAuthError(Exception):
    """Exception for authentication errors."""


class ZControlApiError(Exception):
    """Exception for API errors."""


class ZControlApiClient:
    """API client for Z-Control cloud service."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self._email = email
        self._password = password
        self._auth_token: str | None = None

    @property
    def auth_token(self) -> str | None:
        """Return the current auth token."""
        return self._auth_token

    async def authenticate(self) -> bool:
        """Authenticate with the Z-Control cloud service.

        Returns True if authentication was successful.
        Raises ZControlAuthError on authentication failure.
        """
        try:
            # Step 1: Get login page to extract CSRF token
            async with self._session.get(
                LOGIN_URL,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    raise ZControlAuthError(f"Failed to load login page: {resp.status}")
                html = await resp.text()

            # Extract CSRF token
            match = re.search(
                r'name="__RequestVerificationToken"\s+.*?value="([^"]+)"',
                html,
                re.DOTALL,
            )
            if not match:
                # Try alternative pattern
                match = re.search(
                    r'__RequestVerificationToken.*?value="([^"]+)"',
                    html,
                )
            if not match:
                raise ZControlAuthError("Could not find CSRF token on login page")

            csrf_token = match.group(1)
            _LOGGER.debug("Found CSRF token")

            # Step 2: POST login credentials
            login_data = {
                "__RequestVerificationToken": csrf_token,
                "Email": self._email,
                "password": self._password,
            }

            async with self._session.post(
                LOGIN_URL,
                data=login_data,
                timeout=aiohttp.ClientTimeout(total=30),
                allow_redirects=True,
            ) as resp:
                # Check for successful login (redirects to dashboard)
                if resp.status not in (200, 302):
                    raise ZControlAuthError(f"Login failed with status: {resp.status}")

                # Check response URL - if still on login page, credentials were wrong
                if "login" in str(resp.url).lower() and resp.status == 200:
                    response_text = await resp.text()
                    if "invalid" in response_text.lower() or "error" in response_text.lower():
                        raise ZControlAuthError("Invalid email or password")

            # Step 3: Extract auth token from cookies
            for cookie in self._session.cookie_jar:
                if cookie.key == AUTH_TOKEN_COOKIE:
                    self._auth_token = cookie.value
                    _LOGGER.debug("Successfully obtained auth token")
                    return True

            # If no auth token cookie found, try to get it from response
            raise ZControlAuthError("Authentication succeeded but no auth token received")

        except aiohttp.ClientError as err:
            raise ZControlApiError(f"Connection error during authentication: {err}") from err

    def _get_headers(self) -> dict[str, str]:
        """Get headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "Ocp-Apim-Subscription-Key": SUBSCRIPTION_KEY,
        }
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    async def get_devices(self, device_id: str | None = None) -> list[dict[str, Any]]:
        """Get all devices with their status.

        Returns a list of locations, each containing devices.
        """
        url = f"{API_BASE_URL}/Locations/user/devices/detail"
        if device_id is not None:
            url += f"/{device_id}/0"

        try:
            async with self._session.get(
                url,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise ZControlAuthError("Authentication token expired")
                if resp.status != 200:
                    raise ZControlApiError(f"API error: {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise ZControlApiError(f"Connection error: {err}") from err

    async def get_device_status(self, device_id: str) -> list[dict[str, Any]]:
        """Get the portal detail rows (description/value) for a device."""
        url = f"{API_BASE_URL}/devices/DeviceStatusDetail/{device_id}/WebAppDetail/0"

        try:
            async with self._session.get(
                url,
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise ZControlAuthError("Authentication token expired")
                if resp.status != 200:
                    raise ZControlApiError(f"API error: {resp.status}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise ZControlApiError(f"Connection error: {err}") from err

    async def send_command(self, device_id: str, command: str) -> bool:
        """Send a command to a device.

        Args:
            device_id: The device ID
            command: Either COMMAND_ALARM_SILENCE or COMMAND_DEVICE_RESET

        Returns True if command was successful.
        """
        url = f"{API_BASE_URL}/devices/{device_id}/sendCommandDevice"

        payload = {
            "Command": command,
            "Parameter": None,
        }

        try:
            async with self._session.post(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status == 401:
                    raise ZControlAuthError("Authentication token expired")
                return resp.status == 200
        except aiohttp.ClientError as err:
            raise ZControlApiError(f"Connection error: {err}") from err

    async def silence_alarm(self, device_id: str) -> bool:
        """Silence the alarm on a device."""
        return await self.send_command(device_id, COMMAND_ALARM_SILENCE)

    async def reset_device(self, device_id: str) -> bool:
        """Reset a device."""
        return await self.send_command(device_id, COMMAND_DEVICE_RESET)
