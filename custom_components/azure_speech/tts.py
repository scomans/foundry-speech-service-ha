"""Text to speech support for Azure Speech."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override
from xml.sax.saxutils import escape, quoteattr

import aiohttp

from homeassistant.components.tts import (
    ATTR_PREFERRED_FORMAT,
    ATTR_VOICE,
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AzureSpeechConfigEntry
from .const import DEFAULT_VOICE, DOMAIN, tts_url

PARALLEL_UPDATES = 0

# HA format -> Azure X-Microsoft-OutputFormat
OUTPUT_FORMATS = {
    "mp3": "audio-24khz-48kbitrate-mono-mp3",
    "wav": "riff-24khz-16bit-mono-pcm",
    "ogg": "ogg-24khz-16bit-mono-opus",
}


def _secondary_locales(voice: dict[str, Any]) -> list[str]:
    """Return a voice's extra locales; Azure sends a list, tolerate a CSV string."""
    value = voice.get("SecondaryLocaleList") or []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part) for part in value]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AzureSpeechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the TTS entity."""
    async_add_entities([AzureSpeechTTSEntity(config_entry)])


class AzureSpeechTTSEntity(TextToSpeechEntity):
    """Azure Speech TTS entity."""

    _attr_has_entity_name = True
    _attr_name = "TTS"
    _attr_supported_options = [ATTR_VOICE, ATTR_PREFERRED_FORMAT]

    def __init__(self, entry: AzureSpeechConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._voices_by_locale: dict[str, list[dict[str, Any]]] = {}
        for voice in entry.runtime_data.voices:
            self._voices_by_locale.setdefault(voice["Locale"], []).append(voice)
        self._attr_unique_id = f"{entry.entry_id}-tts"
        self._attr_supported_languages = sorted(self._voices_by_locale)
        self._attr_default_language = (
            "en-US" if "en-US" in self._voices_by_locale else self._attr_supported_languages[0]
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Microsoft",
            model="Azure Speech",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def default_options(self) -> Mapping[str, Any]:
        """Return the default options."""
        return {ATTR_PREFERRED_FORMAT: "mp3"}

    @callback
    @override
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        """Return the voices for a language."""
        voices = [
            *self._voices_by_locale.get(language, []),
            *(
                v
                for v in self._entry.runtime_data.voices
                if language in _secondary_locales(v)
            ),
        ]
        if not voices:
            return None
        unique = {v["ShortName"]: v for v in voices}.values()
        return sorted(
            (Voice(v["ShortName"], v.get("LocalName", v["ShortName"])) for v in unique),
            key=lambda voice: voice.name.casefold(),
        )

    def _voice_for(self, language: str, options: dict[str, Any]) -> tuple[str, str]:
        """Return (voice short name, locale to speak in)."""
        if voice := options.get(ATTR_VOICE):
            for locale, voices in self._voices_by_locale.items():
                for v in voices:
                    if v["ShortName"] == voice:
                        # Multilingual voices can speak the requested language.
                        if language in _secondary_locales(v):
                            return voice, language
                        return voice, locale
            return voice, language
        if voices := self._voices_by_locale.get(language):
            return voices[0]["ShortName"], language
        return DEFAULT_VOICE, "en-US"

    @override
    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """Synthesize speech through the Azure REST API."""
        fmt = options.get(ATTR_PREFERRED_FORMAT, "mp3")
        if fmt in ("ogg", "oga"):
            fmt = "ogg"
        if fmt not in OUTPUT_FORMATS:
            fmt = "mp3"
        voice, locale = self._voice_for(language, options)
        ssml = (
            f"<speak version='1.0' xml:lang={quoteattr(locale)}>"
            f"<voice name={quoteattr(voice)}>{escape(message)}</voice></speak>"
        )
        data = self._entry.runtime_data
        try:
            async with async_get_clientsession(self.hass).post(
                tts_url(data.region),
                headers={
                    "Ocp-Apim-Subscription-Key": data.api_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": OUTPUT_FORMATS[fmt],
                    "User-Agent": "HomeAssistant-AzureSpeech",
                },
                data=ssml.encode("utf-8"),
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                audio = await resp.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(f"Azure Speech TTS failed: {err}") from err
        return fmt, audio
