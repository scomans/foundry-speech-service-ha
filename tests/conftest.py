"""Shared fixtures for the Azure Speech tests."""

from unittest.mock import patch

import pytest
from pytest_homeassistant.common import MockConfigEntry

from custom_components.azure_speech.const import CONF_REGION, DOMAIN, voices_url
from homeassistant.const import CONF_API_KEY

API_KEY = "test-key"
REGION = "westeurope"

VOICES = [
    {
        "ShortName": "en-US-JennyNeural",
        "LocalName": "Jenny",
        "Locale": "en-US",
        "SecondaryLocaleList": ["de-DE"],
    },
    {"ShortName": "en-US-GuyNeural", "LocalName": "Guy", "Locale": "en-US"},
    {"ShortName": "de-DE-KatjaNeural", "LocalName": "Katja", "Locale": "de-DE"},
]
VOICES_URL = voices_url(REGION)


@pytest.fixture(autouse=True)
def _enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load custom_components from this repository."""


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """Use a writable configuration directory, where TTS creates its cache."""
    return hass_tmp_config_dir


@pytest.fixture
def mock_entry() -> MockConfigEntry:
    """Return a config entry for the test region."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Azure Speech",
        data={CONF_API_KEY: API_KEY, CONF_REGION: REGION},
    )


@pytest.fixture
def mock_setup_entry():
    """Skip the real setup after a config flow finishes."""
    with patch(
        "custom_components.azure_speech.async_setup_entry", return_value=True
    ) as mock:
        yield mock
