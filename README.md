# Hermes Voice

Push-to-talk voice interface for Hermes AI, built with **hexagonal architecture**.

It loads the **same context** Hermes loads at startup — your persona (`SOUL.md`),
user profile (`memories/USER.md`), environment notes (`memories/MEMORY.md`), and
configuration — so it feels like talking to the same assistant.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Browser   │────▶│  Voice Gateway  │────▶│  Deepgram   │
│ (Mic+Audio) │◄────│  (WebSocket)   │◄────│   (STT)     │
└─────────────┘     │               │     └─────────────┘
                    │               │
                    │  ┌────────┐ │     ┌─────────────┐
                    │  │Application│ │────▶│  OpenRouter  │
                    │  │ Use Cases│ │◄────│   (LLM)     │
                    │  └────────┘ │     └─────────────┘
                    │      ▲       │
                    │  ┌───┴───┐   │     ┌─────────────┐
                    │  │ Domain │   │────▶│  Cartesia   │
                    │  │ Ports  │   │◄────│   (TTS)     │
                    │  └───────┘   │     └─────────────┘
                    └──────────────┘
                           │
              ┌─────────────────────────────────────────┐
              │         Hermes Context Provider              │
              │  Loads SOUL.md + USER.md + MEMORY.md + config │
              │         (same startup context as Hermes)       │
              └─────────────────────────────────────────┘
                           │
              ┌─────────────────────────────────────────┐
              │         Background Sub-Agent Workers             │
              │   Inherit full HermesContext + conversation     │
              │   Run complex tasks while voice loop stays chatty │
              └─────────────────────────────────────────┘
```

## Architecture

| Layer | Path | Responsibility | External Deps |
|-------|------|--------------|---------------|
| **Domain** | `src/hermes_voice/domain/` | Entities + Ports | None |
| **Application** | `src/hermes_voice/application/` | Use Cases | Domain only |
| **Infrastructure** | `src/hermes_voice/infrastructure/` | Adapters | HTTP clients, APIs, YAML |
| **API** | `src/hermes_voice/api/` | FastAPI + WebSocket + DI | FastAPI, static files |

### Key Features

- **Intent Classification**: Every message is classified (`conversation` / `quick_tool` / `delegate`)
- **Fast Response**: Simple messages get inline LLM responses (<2s)
- **Background Delegation**: Complex tasks spawn async sub-agents. You get an immediate
  *"I'm on it"* ack and can keep talking.
- **Proactive Notifications**: When a background task finishes, the server pushes audio
  to your browser automatically.
- **Shared Hermes Context**: Loads `~/.hermes/SOUL.md`, `~/.hermes/memories/*.md`, and
  `~/.hermes/config.yaml` so the voice agent has the same personality and knowledge.

## Quick Start

### 1. Sign up for API keys

- [Deepgram](https://console.deepgram.com/signup) — Speech-to-Text
- [Cartesia](https://play.cartesia.ai/) — Text-to-Speech
- [OpenRouter](https://openrouter.ai/keys) — LLM (or use your own OpenAI key)

### 2. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your keys
```

Optional: set `HERMES_HOME=/path/to/.hermes` to load your Hermes context.

### 4. Run

```bash
uvicorn hermes_voice.api.main:app --host 0.0.0.0 --port 9120
```

Visit `http://localhost:9120`, hold the button, and talk.

### 5. Test

```bash
pytest -m unit          # fast, no API calls
pytest -m integration   # slow, hits live APIs (requires keys)
```

## Deployment

```bash
./scripts/deploy.sh
```

This installs the systemd service, requests an SSL cert for `voice.dsnoble.com`, and reloads nginx.

## License

MIT
