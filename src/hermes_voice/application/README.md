# Application Layer

Contains **use cases** — the business logic of Hermes Voice.

Rules:
- Depends **ONLY** on the Domain layer (`hermes_voice.domain`)
- Has **NO** knowledge of HTTP, WebSockets, Deepgram, Cartesia, or OpenAI
- All I/O is injected via ports defined in the Domain layer

This makes every use case fully testable with fake (in-memory) adapters.
