"""Build the phrase hint list sent to Azure before recognition."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.homeassistant.exposed_entities import (
    async_should_expose,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from .const import (
    CONF_CUSTOM_PHRASES,
    CONF_HINT_SOURCES,
    DEFAULT_HINT_SOURCES,
    HINT_AREAS,
    HINT_DEVICES,
    HINT_ENTITIES,
    HINT_FLOORS,
    MAX_PHRASES,
)

REGISTRY_EVENTS = (
    er.EVENT_ENTITY_REGISTRY_UPDATED,
    dr.EVENT_DEVICE_REGISTRY_UPDATED,
    ar.EVENT_AREA_REGISTRY_UPDATED,
    fr.EVENT_FLOOR_REGISTRY_UPDATED,
)


class PhraseBuilder:
    """Collect names from Home Assistant registries, cached until they change."""

    def __init__(self, hass: HomeAssistant, options: dict[str, Any]) -> None:
        """Initialize with the entry options."""
        self._hass = hass
        self._sources: set[str] = set(
            options.get(CONF_HINT_SOURCES, DEFAULT_HINT_SOURCES)
        )
        self._custom: list[str] = [
            line.strip()
            for line in (options.get(CONF_CUSTOM_PHRASES) or "").splitlines()
            if line.strip()
        ]
        self._cache: list[str] | None = None
        self._unsubs: list[Callable[[], None]] = []

    @callback
    def async_start_listening(self) -> None:
        """Invalidate the cache whenever a relevant registry changes."""
        for event in REGISTRY_EVENTS:
            self._unsubs.append(self._hass.bus.async_listen(event, self._invalidate))

    @callback
    def async_stop_listening(self) -> None:
        """Stop listening to registry events."""
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()

    @callback
    def _invalidate(self, _event: Any) -> None:
        self._cache = None

    @callback
    def build(self) -> list[str]:
        """Return the deduplicated phrase list (custom phrases first)."""
        if self._cache is None:
            self._cache = self._collect()
        return self._cache

    def _collect(self) -> list[str]:
        names: list[str] = list(self._custom)
        hass = self._hass

        if HINT_FLOORS in self._sources:
            for floor in fr.async_get(hass).async_list_floors():
                names.append(floor.name)
                names.extend(floor.aliases)

        if HINT_AREAS in self._sources:
            for area in ar.async_get(hass).async_list_areas():
                names.append(area.name)
                names.extend(area.aliases)

        if HINT_DEVICES in self._sources:
            for device in dr.async_get(hass).devices.values():
                if device.disabled:
                    continue
                if name := device.name_by_user or device.name:
                    names.append(name)

        if HINT_ENTITIES in self._sources:
            for entry in er.async_get(hass).entities.values():
                if entry.disabled or not async_should_expose(
                    hass, "conversation", entry.entity_id
                ):
                    continue
                if name := entry.name or entry.original_name:
                    names.append(name)
                names.extend(a for a in entry.aliases if isinstance(a, str))

        seen: set[str] = set()
        phrases: list[str] = []
        for name in names:
            name = name.strip()
            if name and (key := name.casefold()) not in seen:
                seen.add(key)
                phrases.append(name)
        return phrases[:MAX_PHRASES]
