# Hermes Voice

Push-to-talk voice interface for Hermes AI, built with **hexagonal architecture**.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Browser   │────▶│  FastAPI API │────▶│  Deepgram   │
│ (Microphone)│◄────│  (Driving    │◄────│   (STT)     │
└─────────────┘     │   Adapter)   │     └─────────────┘
                    │              │
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
```

## Architecture

| Layer | Path | Responsibility | External Deps |
|-------|------|--------------|---------------|
| **Domain** | `src/hermes_voice/domain/` | Entities + Ports | None |
| **Application** | `src/hermes_voice/application/` | Use Cases | Domain only |
| **Infrastructure** | `src/hermes_voice/infrastructure/` | Adapters | HTTP clients, APIs |
| **API** | `src/hermes_voice/api/` | FastAPI + WebSocket + DI | FastAPI, static files |

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
