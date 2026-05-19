# Infrastructure Layer

Adapters that implement the **ports** defined in the Domain layer.

This is where all external dependencies live:
- HTTP clients (httpx)
- Third-party APIs (Deepgram, Cartesia, OpenRouter)
- Persistence (in-memory dict, Redis, Postgres, etc.)

Swapping adapters requires **zero changes** to Domain or Application code.
