# Vibe Coding Stack Setup (Continue + OpenCode)

This folder contains starter configuration files for the hackathon vibe-coding setup.

Each team receives one OpenRouter API key with a budget limit of 20€.

You can use your OpenRouter API key however you like. To make onboarding easier, we provide ready-to-use config files and instructions for:

* Continue.dev for VS Code
* OpenCode for terminal-based agentic coding

The provided configurations use models that are reasonably priced while still being powerful enough for productive hacking.

-> You can check your remaining credits like described [here](https://openrouter.ai/docs/api/reference/limits)

---

# Important

* Do not commit your API key.
* Do not share your API key with other teams.
* Your team has a 20 € budget limit for the hackathon.
* This should be enough for one day of hacking, but agentic coding can consume budget quickly.

To avoid burning through your budget too fast:

* Start with the default cheaper model.
* Use premium models only when needed.
* Avoid long-running agent loops.
* Avoid prompts like “keep going until everything is perfect”.
* Break work into smaller tasks.

---

# Setup

# Continue.dev (VS Code)

Continue is an open-source AI coding assistant similar to GitHub Copilot.

## Install

1. Install VS Code
2. Install the Continue extension:
   [https://marketplace.visualstudio.com/items?itemName=Continue.continue](https://marketplace.visualstudio.com/items?itemName=Continue.continue)

## Configure

1. Add your API key to the config
2. We have prepared a example configuration. You can copy it from `continue/config.yaml` to your local continue config dir `~/.continue/config.yaml`
3. Restart VS Code after copying the config.

# OpenCode

OpenCode is an open-source terminal-based AI coding agent.

## Install

Follow the installation instructions: [https://opencode.ai/docs](https://opencode.ai/docs)

- To use your Open Router API key, type `\connect` and choose OpenRouter

# Recommended usage

- Cheap models like DeepSeek as your default model
- Qwen Free models for experimentation
- Expensive models like Claude Sonnet sparsely

Yet feel free to add any models you want to use from https://openrouter.ai/models
