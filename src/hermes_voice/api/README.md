# API Layer (Driving Adapter + Composition Root)

This is the **entry point** of the application.

Responsibilities:
- Parse environment configuration
- Wire concrete adapters into domain ports
- Expose FastAPI HTTP/WebSocket endpoints
- Serve the static frontend

Nothing in `Domain` or `Application` knows FastAPI exists.
