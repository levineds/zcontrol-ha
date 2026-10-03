"""Local Home Assistant fixtures; no live cloud or pump connections."""

from inspect import signature

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import frame
import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def hass(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    if hasattr(frame, "async_setup"):
        frame.async_setup(hass)
    yield hass
    await hass.async_stop()


@pytest.fixture
def make_config_entry():
    """Construct real entries across the supported Home Assistant versions."""

    def create(**kwargs):
        if "subentries_data" in signature(ConfigEntry).parameters:
            kwargs["subentries_data"] = None
        return ConfigEntry(**kwargs)

    return create
