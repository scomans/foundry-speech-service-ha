"""Config flow tests."""

from http import HTTPStatus

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from custom_components.azure_speech.const import CONF_REGION, DOMAIN, voices_url
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import API_KEY, REGION, VOICES, VOICES_URL

USER_INPUT = {CONF_API_KEY: API_KEY, CONF_REGION: " WestEurope ", CONF_NAME: "Speech"}


async def _start(hass: HomeAssistant):
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


async def test_user_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
) -> None:
    """A valid key and region create an entry with a normalised region."""
    aioclient_mock.get(VOICES_URL, json=VOICES)
    result = await _start(hass)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Speech"
    assert result["data"] == {CONF_API_KEY: API_KEY, CONF_REGION: REGION}


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (HTTPStatus.UNAUTHORIZED, "invalid_auth"),
        (HTTPStatus.FORBIDDEN, "invalid_auth"),
        (HTTPStatus.NOT_FOUND, "invalid_region"),
        (HTTPStatus.INTERNAL_SERVER_ERROR, "cannot_connect"),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_setup_entry,
    status: HTTPStatus,
    error: str,
) -> None:
    """Failures are reported on the form and the flow can be retried."""
    aioclient_mock.get(VOICES_URL, status=status)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    aioclient_mock.clear_requests()
    aioclient_mock.get(VOICES_URL, json=VOICES)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_entry: MockConfigEntry
) -> None:
    """The same key and region cannot be added twice."""
    mock_entry.add_to_hass(hass)
    result = await _start(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    mock_setup_entry,
) -> None:
    """Reauthentication stores the new key."""
    mock_entry.add_to_hass(hass)
    aioclient_mock.get(VOICES_URL, json=VOICES)
    result = await mock_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "new-key"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data[CONF_API_KEY] == "new-key"


async def test_reconfigure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    mock_setup_entry,
) -> None:
    """Reconfiguring changes key and region."""
    mock_entry.add_to_hass(hass)
    aioclient_mock.get(voices_url("northeurope"), json=VOICES)
    result = await mock_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "other", CONF_REGION: "NorthEurope"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_entry.data == {CONF_API_KEY: "other", CONF_REGION: "northeurope"}


async def test_options_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    mock_entry: MockConfigEntry,
    mock_setup_entry,
) -> None:
    """The options flow saves the phrase hint settings."""
    mock_entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(mock_entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"phrase_hints": False, "hint_sources": ["areas"], "custom_phrases": "Foo"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_entry.options["phrase_hints"] is False
