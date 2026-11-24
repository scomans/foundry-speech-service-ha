---
name: Bug report
about: Something does not work as described
labels: bug
---

**What happened?**

**What did you expect?**

**Environment**
- Home Assistant version:
- Integration version:
- Azure Speech region:
- Affected feature (speech-to-text, text-to-speech, phrase hints):

**Debug log**

Enable debug logging, reproduce the problem, and paste the lines containing `custom_components.azure_speech`
(remove any keys first):

```yaml
logger:
  logs:
    custom_components.azure_speech: debug
```
