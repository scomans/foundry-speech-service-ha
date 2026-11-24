"""Constants for the Azure Speech integration."""

import logging

DOMAIN = "azure_speech"
LOGGER = logging.getLogger(__package__)

CONF_REGION = "region"
CONF_VOICE = "voice"

CONF_PHRASE_HINTS = "phrase_hints"
CONF_HINT_SOURCES = "hint_sources"
CONF_CUSTOM_PHRASES = "custom_phrases"

HINT_FLOORS = "floors"
HINT_AREAS = "areas"
HINT_DEVICES = "devices"
HINT_ENTITIES = "exposed_entities"
HINT_SOURCES = [HINT_FLOORS, HINT_AREAS, HINT_DEVICES, HINT_ENTITIES]
DEFAULT_HINT_SOURCES = [HINT_AREAS, HINT_ENTITIES]
# Keep requests small; Azure also limits phrase list size.
MAX_PHRASES = 500

DEFAULT_NAME = "Azure Speech"
DEFAULT_VOICE = "en-US-JennyNeural"

# Regions offering the Speech service:
# https://learn.microsoft.com/azure/ai-services/speech-service/regions
REGIONS: list[str] = [
    "australiaeast",
    "brazilsouth",
    "canadacentral",
    "centralindia",
    "centralus",
    "eastasia",
    "eastus",
    "eastus2",
    "francecentral",
    "germanywestcentral",
    "japaneast",
    "japanwest",
    "koreacentral",
    "northcentralus",
    "northeurope",
    "norwayeast",
    "southafricanorth",
    "southcentralus",
    "southeastasia",
    "swedencentral",
    "switzerlandnorth",
    "uaenorth",
    "uksouth",
    "westcentralus",
    "westeurope",
    "westus",
    "westus2",
    "westus3",
]


def stt_url(region: str) -> str:
    """Short-audio speech-to-text REST endpoint."""
    return (
        f"https://{region}.stt.speech.microsoft.com"
        "/speech/recognition/conversation/cognitiveservices/v1"
    )


def fast_transcription_url(region: str) -> str:
    """Fast Transcription endpoint, the only STT API that accepts phrase lists."""
    return (
        f"https://{region}.api.cognitive.microsoft.com"
        "/speechtotext/transcriptions:transcribe?api-version=2024-11-15"
    )


def tts_url(region: str) -> str:
    """Text-to-speech REST endpoint."""
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"


def voices_url(region: str) -> str:
    """Voice list endpoint, also used to validate credentials."""
    return f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
