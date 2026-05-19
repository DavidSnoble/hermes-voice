# Hermes Voice

Push-to-talk voice interface for Hermes AI, built with **hexagonal architecture**.

It loads your **personality and user context** from Hermes (`SOUL.md`, `USER.md`) so it
sounds like the same assistant — but it stays **lightweight**. Complex tasks are
delegated to the full Hermes gateway via its built-in API server.

```
Voice App (lightweight)                    Hermes Gateway (full power)
┌───────────────────────┐                 ┌───────────────────────┐
│  Browser (push-to-talk)  │                 │  Hermes Gateway          │
│  → Deepgram STT          │                 │  → All tools & skills    │
│  → Cartesia TTS          │                 │  → Full agent loop       │
│  → 2-3 fast tools        │                 │  → Memory & context      │
│  → Intent classifier     │                 │  → Personality           │
└─────────────┼─────────────┘                 └───────────────────────┘
           │                                          ▲
           │    POST /v1/runs (delegate complex task)
           └────────────────────────────────────────┴─────────────
              GET /v1/runs/{id} (poll for completion)
```

## Architecture

| Layer | Path | Responsibility | External Deps |
|-------|------|--------------|---------------|
| **Domain** | `src/hermes_voice/domain/` | Entities + Ports | None |
| **Application** | `src/hermes_voice/application/` | Use Cases | Domain only |
| **Infrastructure** | `src/hermes_voice/infrastructure/` | Adapters | HTTP clients, APIs |
| **API** | `src/hermes_voice/api/` | FastAPI + WebSocket + DI | FastAPI, static files |

### Key Design Decisions

- **Lightweight voice agent**: Only loads persona (`SOUL.md`) + user profile (`USER.md`).
  Does NOT load the full tool registry into its system prompt.
- **Intent classification**: Every message is classified (`conversation` / `quick_tool` / `delegate`)
- **Fast path**: Simple messages get inline LLM responses (<2s)
- **Delegation path**: Complex tasks are sent to the Hermes gateway's `/v1/runs` API.
  The full Hermes agent (with ALL tools, skills, memory) handles it.
- **Proactive audio**: When a Hermes task finishes, the server pushes audio to your
  browser automatically.

## Prerequisites: Enable Hermes API Server

The voice app delegates complex tasks to your existing Hermes gateway. The gateway must have its built-in API server enabled.

**Good news**: if your Hermes is already running, the API server is likely already active on port 8642. Verify:

```bash
curl http://127.0.0.1:8642/health
```

If you see `{"status": "ok"}`, you're ready.

If not, set these environment variables and restart:

```bash
export API_SERVER_ENABLED=true
export API_SERVER_KEY=your_secret_key_here
export API_SERVER_PORT=8642
export API_SERVER_HOST=127.0.0.1
systemctl restart hermes-gateway
```

## Quick Start

### 1. Sign up for API keys

You only need **2 external keys** (not 3). The voice app uses your existing Hermes gateway for LLM calls, so no separate OpenRouter/opencode-go key is needed.

| Service | What it does | Sign up |
|---------|-------------|---------|
| **Deepgram** | Speech-to-Text | [console.deepgram.com/signup](https://console.deepgram.com/signup) |
| **Cartesia** | Text-to-Speech | [play.cartesia.ai](https://play.cartesia.ai/) |

The voice app will use your Hermes gateway (already running on `localhost:8642`) as its LLM backend.

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

Make sure `HERMES_API_KEY` matches the `API_SERVER_KEY` you set for Hermes.

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

This installs the systemd service, requests an SSL cert for `voice.dsnoble.com`,
and reloads nginx.

## License

MIT
