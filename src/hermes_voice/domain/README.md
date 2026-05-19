# Domain Layer

The core of Hermes Voice. **Zero external dependencies.**

Owns:
- **Entities**: `Conversation`, `Message`, `AudioInput`, `AudioOutput`, `Transcript`
- **Ports**: Interfaces that define what the domain needs from the outside world

The domain does not know about HTTP, WebSockets, Deepgram, Cartesia, OpenAI, or FastAPI.
It only knows: "I have audio, I need text" and "I have text, I need audio back."

Adapters in the Infrastructure layer will implement these ports.
