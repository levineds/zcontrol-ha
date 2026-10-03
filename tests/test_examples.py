"""Validate notification examples with Home Assistant's schemas and templates."""

from pathlib import Path
from types import SimpleNamespace

from homeassistant.components.automation.config import PLATFORM_SCHEMA
from homeassistant.components.homeassistant.triggers.state import TRIGGER_STATE_SCHEMA
from homeassistant.core import State
from homeassistant.helpers.template import Template
import pytest
import yaml

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filename",
    [
        "508_fault_alert.yaml",
        "apak_input_alert.yaml",
        "offline_alert.yaml",
    ],
)
async def test_notification_examples(filename, hass):
    """Accept complete automations and render messages for an actual state trigger."""
    config = PLATFORM_SCHEMA(yaml.safe_load((EXAMPLES / filename).read_text()))
    for trigger in config.get("triggers", config.get("trigger")):
        validated = TRIGGER_STATE_SCHEMA(trigger)
        entity_id = validated["entity_id"][0]
        state = State(entity_id, trigger["to"], {"friendly_name": "Test sump status"})
        variables = {"trigger": SimpleNamespace(entity_id=entity_id, to_state=state)}
        for action in config.get("actions", config.get("action")):
            assert (
                action.get("action", action.get("service"))
                == "persistent_notification.create"
            )
            for value in action["data"].values():
                template = (
                    value if isinstance(value, Template) else Template(value, hass)
                )
                template.hass = hass
                rendered = template.async_render(variables)
            assert rendered
