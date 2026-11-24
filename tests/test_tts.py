"""Text-to-speech tests."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.azure_speech.const import tts_url
from custom_components.azure_speech.tts import AzureSpeechTTSEntity
from homeassistant.core import HomeAssistant

from .conftest import REGION, VOICES, VOICES_URL


@pytest.fixture
async def entity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
) -> AzureSpeechTTSEntity:
    """Return a TTS entity backed by a loaded entry."""
    aioclient_mock.get(VOICES_URL, json=VOICES)
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    tts = AzureSpeechTTSEntity(mock_entry)
    tts.hass = hass
    return tts


async def test_languages_and_voices(entity: AzureSpeechTTSEntity) -> None:
    """Languages and voices come from the voice catalogue."""
    assert entity.supported_languages == ["de-DE", "en-US"]
    assert entity.default_language == "en-US"
    # Jenny is multilingual and also offered for German.
    names = [v.voice_id for v in entity.async_get_supported_voices("de-DE")]
    assert names == ["en-US-JennyNeural", "de-DE-KatjaNeural"]
    assert entity.async_get_supported_voices("fr-FR") is None


async def test_voice_selection(entity: AzureSpeechTTSEntity) -> None:
    """Explicit voices win, multilingual voices speak the requested language."""
    assert entity._voice_for("en-US", {}) == ("en-US-JennyNeural", "en-US")
    assert entity._voice_for("de-DE", {}) == ("de-DE-KatjaNeural", "de-DE")
    assert entity._voice_for("de-DE", {"voice": "en-US-JennyNeural"}) == (
        "en-US-JennyNeural",
        "de-DE",
    )
    assert entity._voice_for("fr-FR", {}) == ("en-US-JennyNeural", "en-US")


async def test_synthesis(
    entity: AzureSpeechTTSEntity, aioclient_mock: AiohttpClientMocker
) -> None:
    """The request carries SSML with escaped text and the requested format."""
    aioclient_mock.post(tts_url(REGION), content=b"audio")
    fmt, audio = await entity.async_get_tts_audio(
        "a < b", "en-US", {"preferred_format": "wav"}
    )
    assert (fmt, audio) == ("wav", b"audio")
    _, _, body, headers = aioclient_mock.mock_calls[-1]
    assert b"a &lt; b" in body
    assert headers["X-Microsoft-OutputFormat"] == "riff-24khz-16bit-mono-pcm"
