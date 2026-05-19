from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from hermes_voice.api.websocket_handler import handle_voice_websocket


def create_app() -> FastAPI:
    app = FastAPI(title="Hermes Voice", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["https://voice.dsnoble.com", "http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def root() -> FileResponse:
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return HTMLResponse(content="<h1>Hermes Voice API</h1><p>Static files not built.</p>")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.websocket("/ws")
    async def voice_ws(websocket: WebSocket) -> None:
        await handle_voice_websocket(websocket)

    return app


app = create_app()
