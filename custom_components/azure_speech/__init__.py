"""The Azure Speech integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_PHRASE_HINTS, CONF_REGION, DOMAIN, voices_url
from .phrase_builder import PhraseBuilder

PLATFORMS = (Platform.STT, Platform.TTS)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class AzureSpeechData:
    """Runtime data: credentials plus the voice catalogue."""

    api_key: str
    region: str
    voices: list[dict[str, Any]]
    phrase_builder: PhraseBuilder
    phrase_hints: bool


type AzureSpeechConfigEntry = ConfigEntry[AzureSpeechData]


async def async_fetch_voices(
    hass: HomeAssistant, api_key: str, region: str
) -> list[dict[str, Any]]:
    """Fetch the voice list; raises aiohttp.ClientResponseError on 401/403 etc."""
    session = async_get_clientsession(hass)
    async with session.get(
        voices_url(region),
        headers={"Ocp-Apim-Subscription-Key": api_key},
        timeout=aiohttp.ClientTimeout(total=15),
    ) as resp:
        resp.raise_for_status()
        return await resp.json()


async def async_setup_entry(hass: HomeAssistant, entry: AzureSpeechConfigEntry) -> bool:
    """Set up Azure Speech from a config entry."""
    api_key, region = entry.data[CONF_API_KEY], entry.data[CONF_REGION]
    try:
        voices = await async_fetch_voices(hass, api_key, region)
    except aiohttp.ClientResponseError as err:
        if err.status in (401, 403):
            raise ConfigEntryAuthFailed(err) from err
        raise ConfigEntryNotReady(err) from err
    except (aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(err) from err

    builder = PhraseBuilder(hass, dict(entry.options))
    builder.async_start_listening()
    entry.async_on_unload(builder.async_stop_listening)
    entry.runtime_data = AzureSpeechData(
        api_key,
        region,
        voices,
        builder,
        entry.options.get(CONF_PHRASE_HINTS, True),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def _async_options_updated(
    hass: HomeAssistant, entry: AzureSpeechConfigEntry
) -> None:
    """Reload so the phrase builder picks up new options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: AzureSpeechConfigEntry
) -> bool:
    """Unload Azure Speech."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
