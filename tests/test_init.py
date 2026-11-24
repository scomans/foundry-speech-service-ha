"""Setup and unload tests."""

from http import HTTPStatus

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import VOICES, VOICES_URL


async def test_setup_and_unload(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """The entry loads both platforms and unloads cleanly."""
    aioclient_mock.get(VOICES_URL, json=VOICES)
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("tts.azure_speech_tts")
    assert hass.states.get("stt.azure_speech_stt")

    assert await hass.config_entries.async_unload(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_invalid_key_starts_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """A rejected key puts the entry into setup error and starts reauth."""
    aioclient_mock.get(VOICES_URL, status=HTTPStatus.UNAUTHORIZED)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.SETUP_ERROR
    assert any(
        flow["context"]["source"] == "reauth"
        for flow in hass.config_entries.flow.async_progress()
    )


async def test_setup_unreachable_retries(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> None:
    """A server error is retried later."""
    aioclient_mock.get(VOICES_URL, status=HTTPStatus.INTERNAL_SERVER_ERROR)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
