"""Config flow for Azure Speech (key + region, with reauth and reconfigure)."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import probatio

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import async_fetch_voices
from .const import (
    CONF_CUSTOM_PHRASES,
    CONF_HINT_SOURCES,
    CONF_PHRASE_HINTS,
    CONF_REGION,
    DEFAULT_HINT_SOURCES,
    DEFAULT_NAME,
    DOMAIN,
    HINT_SOURCES,
    REGIONS,
)

_LOGGER = logging.getLogger(__name__)

KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
REGION_SELECTOR = SelectSelector(
    SelectSelectorConfig(
        options=REGIONS, mode=SelectSelectorMode.DROPDOWN, custom_value=True
    )
)

STEP_USER_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): KEY_SELECTOR,
        probatio.Required(CONF_REGION): REGION_SELECTOR,
        probatio.Optional(CONF_NAME, default=DEFAULT_NAME): str,
    }
)
STEP_REAUTH_SCHEMA = probatio.Schema(
    {probatio.Required(probatio.Secret(CONF_API_KEY)): KEY_SELECTOR}
)
STEP_RECONFIGURE_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_API_KEY)): KEY_SELECTOR,
        probatio.Required(CONF_REGION): REGION_SELECTOR,
    }
)


class AzureSpeechOptionsFlow(OptionsFlow):
    """Phrase hint options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure phrase hints."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        schema = probatio.Schema(
            {
                probatio.Required(CONF_PHRASE_HINTS, default=True): bool,
                probatio.Required(
                    CONF_HINT_SOURCES, default=DEFAULT_HINT_SOURCES
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=HINT_SOURCES,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                        translation_key=CONF_HINT_SOURCES,
                    )
                ),
                probatio.Optional(CONF_CUSTOM_PHRASES): TextSelector(
                    TextSelectorConfig(multiline=True, type=TextSelectorType.TEXT)
                ),
            }
        )
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
        )


class AzureSpeechConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Azure Speech."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return AzureSpeechOptionsFlow()

    async def _validate(self, api_key: str, region: str) -> str | None:
        """Return an error key, or None if the credentials work."""
        try:
            await async_fetch_voices(self.hass, api_key, region)
        except aiohttp.ClientResponseError as err:
            if err.status in (401, 403):
                return "invalid_auth"
            if err.status == 404:
                return "invalid_region"
            return "cannot_connect"
        except (aiohttp.ClientError, TimeoutError):
            # An unknown region fails DNS resolution, which lands here too.
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the Speech resource key and region."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[CONF_REGION] = user_input[CONF_REGION].strip().lower()
            self._async_abort_entries_match(
                {
                    CONF_API_KEY: user_input[CONF_API_KEY],
                    CONF_REGION: user_input[CONF_REGION],
                }
            )
            if error := await self._validate(
                user_input[CONF_API_KEY], user_input[CONF_REGION]
            ):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_REGION: user_input[CONF_REGION],
                    },
                )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Start reauthentication after an authorization failure."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new key for the existing region."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            if error := await self._validate(
                user_input[CONF_API_KEY], entry.data[CONF_REGION]
            ):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_API_KEY: user_input[CONF_API_KEY]}
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={CONF_REGION: entry.data[CONF_REGION]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change key and/or region."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            user_input[CONF_REGION] = user_input[CONF_REGION].strip().lower()
            if error := await self._validate(
                user_input[CONF_API_KEY], user_input[CONF_REGION]
            ):
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates=user_input
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                STEP_RECONFIGURE_SCHEMA,
                user_input or {CONF_REGION: entry.data[CONF_REGION]},
            ),
            errors=errors,
        )
