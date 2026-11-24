# Azure Speech for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Validate](https://github.com/scomans/foundry-speech-service-ha/actions/workflows/validate.yml/badge.svg)](https://github.com/scomans/foundry-speech-service-ha/actions/workflows/validate.yml)
[![Tests](https://github.com/scomans/foundry-speech-service-ha/actions/workflows/tests.yml/badge.svg)](https://github.com/scomans/foundry-speech-service-ha/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Unofficial Home Assistant integration that adds **speech-to-text** and **text-to-speech** powered by the
[Azure Speech service](https://learn.microsoft.com/azure/ai-services/speech-service/) (Azure AI Foundry). Use it as the
speech engine of your Assist voice pipelines.

> **Unofficial.** This project is not affiliated with, endorsed by or supported by Microsoft.
> Brand names and logos belong to their owners.

## Features

- Text-to-speech with every voice of your region's catalogue, including multilingual voices
- Speech-to-text for all locales the catalogue offers (WAV/PCM and OGG/Opus input)
- Optional **phrase hints**: names of your floors, areas, devices and entities exposed to Assist (plus your own phrases)
  are sent along with each recording, so Azure recognises them more reliably
- Key and region setup with reauthentication and reconfiguration

## Requirements

- Home Assistant 2026.11 or newer
- An Azure [Speech resource](https://portal.azure.com/#create/Microsoft.CognitiveServicesSpeechServices) (the free F0
  tier works). You need one of its keys and its region.

## Installation

### HACS (custom repository)

[![Open your Home Assistant instance and open this repository in the Marketplace.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=scomans&repository=foundry-speech-service-ha&category=integration)

Use the button above, or add the repository by hand:

1. In HACS open the three-dot menu, choose **Custom repositories** and add
   `https://github.com/scomans/foundry-speech-service-ha` as category **Integration**.
2. Install **Azure Speech** and restart Home Assistant.

### Manual

1. Copy the folder `custom_components/azure_speech` of this repository to `<config>/custom_components/azure_speech`.
2. Restart Home Assistant.

## Setup

1. Go to **Settings > Devices & services > Add integration > Azure Speech**.
2. Enter **Key 1** or **Key 2** and the **region** from the resource's *Keys and Endpoint* page (for example
   `westeurope`).
3. In **Settings > Voice assistants** pick the new **STT** and **TTS** entities for your pipeline.

Wrong key? Home Assistant starts a reauthentication. Use **Reconfigure** on the integration to change key or region.

### Options

**Settings > Devices & services > Azure Speech > Configure**

| Option | Default | Description |
|---|---|---|
| Enable phrase hints | on | Send a phrase list with each recording. This uses Azure's Fast Transcription API; if it fails, plain recognition without hints is used. |
| Collect names from | areas, entities exposed to Assist | Floors, areas, devices and/or entities exposed to Assist. |
| Custom phrases | empty | One phrase per line, for words that are often misrecognised. |

At most 500 phrases are sent per recording.

## Entities

| Entity | Description |
|---|---|
| `stt.azure_speech_stt` | Speech-to-text. |
| `tts.azure_speech_tts` | Text-to-speech. Supports the `voice` option and the output formats `mp3` (default), `wav` and `ogg`. |

## Privacy

Audio recordings, text to speak and (with phrase hints on) the phrase list are sent to the Azure Speech service in the
region you configured. Nothing is sent anywhere else.

## Development

```sh
python -m pip install -r requirements-test.txt
python -m ruff check .
python -m pytest
```

CI runs the same checks plus [hassfest](https://developers.home-assistant.io/blog/2020/04/16/hassfest) and the
[HACS validation](https://hacs.xyz/docs/publish/action/).

## License

[MIT](LICENSE)
