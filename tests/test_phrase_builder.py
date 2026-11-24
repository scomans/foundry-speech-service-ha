"""Phrase builder tests."""

from custom_components.azure_speech.const import MAX_PHRASES
from custom_components.azure_speech.phrase_builder import PhraseBuilder
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, floor_registry as fr


async def test_collects_names_and_deduplicates(hass: HomeAssistant) -> None:
    """Custom phrases come first, duplicates are dropped case-insensitively."""
    floor = fr.async_get(hass).async_create("Ground floor", aliases={"Downstairs"})
    ar.async_get(hass).async_create("Kitchen", floor_id=floor.floor_id)
    builder = PhraseBuilder(
        hass,
        {
            "hint_sources": ["floors", "areas"],
            "custom_phrases": "Zigbee\n\n kitchen \n",
        },
    )
    phrases = builder.build()
    assert phrases[:2] == ["Zigbee", "kitchen"]
    assert {"Ground floor", "Downstairs"} <= set(phrases)
    assert phrases.count("kitchen") == 1


async def test_cache_is_invalidated_by_registry_changes(hass: HomeAssistant) -> None:
    """A registry change makes the next build() see the new area."""
    builder = PhraseBuilder(hass, {"hint_sources": ["areas"]})
    builder.async_start_listening()
    assert builder.build() == []
    ar.async_get(hass).async_create("Garage")
    await hass.async_block_till_done()
    assert builder.build() == ["Garage"]
    builder.async_stop_listening()


async def test_limit(hass: HomeAssistant) -> None:
    """The list is capped to what Azure accepts."""
    lines = "\n".join(f"phrase {i}" for i in range(MAX_PHRASES + 50))
    builder = PhraseBuilder(hass, {"hint_sources": [], "custom_phrases": lines})
    assert len(builder.build()) == MAX_PHRASES
