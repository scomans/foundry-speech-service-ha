"""Speech to text support for Azure Speech (short-audio REST API)."""

from __future__ import annotations

from collections.abc import AsyncIterable
import io
import json
import logging
from typing import override
import wave

import aiohttp

from homeassistant.components import stt
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AzureSpeechConfigEntry
from .const import DOMAIN, fast_transcription_url, stt_url

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AzureSpeechConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the STT entity."""
    async_add_entities([AzureSpeechSTTEntity(config_entry)])


class AzureSpeechSTTEntity(stt.SpeechToTextEntity):
    """Azure Speech to text entity."""

    _attr_has_entity_name = True
    _attr_name = "STT"

    def __init__(self, entry: AzureSpeechConfigEntry) -> None:
        """Initialize the entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}-stt"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Microsoft",
            model="Azure Speech",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def supported_languages(self) -> list[str]:
        """Return languages; Azure accepts the locales of its voice catalogue."""
        return sorted({v["Locale"] for v in self._entry.runtime_data.voices})

    @property
    @override
    def supported_formats(self) -> list[stt.AudioFormats]:
        """Return a list of supported formats."""
        return [stt.AudioFormats.WAV, stt.AudioFormats.OGG]

    @property
    @override
    def supported_codecs(self) -> list[stt.AudioCodecs]:
        """Return a list of supported codecs."""
        return [stt.AudioCodecs.PCM, stt.AudioCodecs.OPUS]

    @property
    @override
    def supported_bit_rates(self) -> list[stt.AudioBitRates]:
        """Return a list of supported bit rates."""
        return [stt.AudioBitRates.BITRATE_16]

    @property
    @override
    def supported_sample_rates(self) -> list[stt.AudioSampleRates]:
        """Return a list of supported sample rates."""
        return [stt.AudioSampleRates.SAMPLERATE_8000, stt.AudioSampleRates.SAMPLERATE_16000]

    @property
    @override
    def supported_channels(self) -> list[stt.AudioChannels]:
        """Return a list of supported channels."""
        return [stt.AudioChannels.CHANNEL_MONO]

    async def _fast_transcribe(
        self,
        metadata: stt.SpeechMetadata,
        body: bytes,
        content_type: str,
        phrases: list[str],
    ) -> str | None:
        """Transcribe with the phrase list; return None on any failure."""
        data = self._entry.runtime_data
        definition = {
            "locales": [metadata.language],
            "phraseList": {"phrases": phrases},
        }
        form = aiohttp.FormData()
        form.add_field(
            "audio",
            body,
            filename="audio.wav" if metadata.format == stt.AudioFormats.WAV else "audio.ogg",
            content_type=content_type.split(";")[0],
        )
        form.add_field("definition", json.dumps(definition))
        try:
            async with async_get_clientsession(self.hass).post(
                fast_transcription_url(data.region),
                headers={"Ocp-Apim-Subscription-Key": data.api_key},
                data=form,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Azure Fast Transcription failed: %s", err)
            return None
        combined = result.get("combinedPhrases") or []
        return combined[0].get("text") or None if combined else None

    @override
    async def async_process_audio_stream(
        self, metadata: stt.SpeechMetadata, stream: AsyncIterable[bytes]
    ) -> stt.SpeechResult:
        """Send the utterance to Azure and return the transcript."""
        audio = bytearray()
        async for chunk in stream:
            audio.extend(chunk)

        if metadata.format == stt.AudioFormats.WAV:
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(metadata.channel.value)
                wf.setsampwidth(metadata.bit_rate.value // 8)
                wf.setframerate(metadata.sample_rate.value)
                wf.writeframes(bytes(audio))
            body = buf.getvalue()
            content_type = (
                f"audio/wav; codecs=audio/pcm; samplerate={metadata.sample_rate.value}"
            )
        else:
            body = bytes(audio)
            content_type = "audio/ogg; codecs=opus"

        data = self._entry.runtime_data
        phrases = data.phrase_builder.build() if data.phrase_hints else []
        if phrases:
            # Only Fast Transcription accepts phrase lists.
            text = await self._fast_transcribe(
                metadata, body, content_type, phrases
            )
            if text:
                return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)
            _LOGGER.debug("Fast Transcription failed, using the short-audio API")

        try:
            async with async_get_clientsession(self.hass).post(
                stt_url(data.region),
                params={"language": metadata.language, "format": "simple"},
                headers={
                    "Ocp-Apim-Subscription-Key": data.api_key,
                    "Content-Type": content_type,
                    "Accept": "application/json",
                },
                data=body,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                result = await resp.json()
        except (aiohttp.ClientError, TimeoutError):
            _LOGGER.exception("Error during Azure Speech STT")
            return stt.SpeechResult(None, stt.SpeechResultState.ERROR)

        if result.get("RecognitionStatus") == "Success" and (
            text := result.get("DisplayText")
        ):
            return stt.SpeechResult(text, stt.SpeechResultState.SUCCESS)
        _LOGGER.debug("Azure Speech did not recognise speech: %s", result)
        return stt.SpeechResult(None, stt.SpeechResultState.ERROR)
