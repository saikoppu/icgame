from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import GameEngine


class JoinRequest(BaseModel):
    name: str = Field(min_length=1, max_length=40)


class GameServer:
    def __init__(self, engine: GameEngine, tick_rate_seconds: float = 1.0) -> None:
        self.engine = engine
        self.tick_rate_seconds = tick_rate_seconds
        self.lock = asyncio.Lock()
        self.connections: dict[str, set[WebSocket]] = {}
        self._shutdown = asyncio.Event()
        self._clock_task: asyncio.Task[None] | None = None

        static_dir = Path(__file__).resolve().parent / "static"

        app = FastAPI(title="Bet Sizing Multiplayer Game", version="1.0.0")
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

        @app.get("/")
        async def index() -> FileResponse:
            return FileResponse(static_dir / "index.html")

        @app.get("/health")
        async def health() -> dict[str, str]:
            return {"status": "ok"}

        @app.get("/api/events")
        async def events() -> dict[str, Any]:
            return {
                "events": self.engine.event_catalog(),
                "lobby_seconds": self.engine.lobby_seconds,
                "starting_bankroll": self.engine.starting_bankroll,
                "round_stipend": self.engine.round_stipend,
            }

        @app.post("/api/join")
        async def join(payload: JoinRequest) -> dict[str, Any]:
            async with self.lock:
                player = self.engine.join_player(payload.name)
                state = self.engine.public_state_for(player.token)
            await self.broadcast_all_states()
            return {"token": player.token, "state": state}

        @app.get("/api/state/{token}")
        async def state(token: str) -> dict[str, Any]:
            async with self.lock:
                if token not in self.engine.players:
                    return {"error": "unknown session"}
                return {"state": self.engine.public_state_for(token)}

        @app.websocket("/ws/{token}")
        async def websocket_endpoint(websocket: WebSocket, token: str) -> None:
            await websocket.accept()

            async with self.lock:
                if token not in self.engine.players:
                    await websocket.send_json({"type": "error", "message": "Unknown player session."})
                    await websocket.close(code=4401)
                    return
                self.connections.setdefault(token, set()).add(websocket)
                state = self.engine.public_state_for(token)

            await websocket.send_json({"type": "state", "payload": state})

            try:
                while True:
                    msg = await websocket.receive_json()
                    if not isinstance(msg, dict):
                        continue

                    msg_type = msg.get("type")
                    if msg_type == "place_bet":
                        option = str(msg.get("option", ""))
                        try:
                            amount = int(msg.get("amount", 0))
                        except (TypeError, ValueError):
                            await websocket.send_json({"type": "error", "message": "Amount must be an integer."})
                            continue
                        try:
                            async with self.lock:
                                self.engine.place_bet(token=token, option_key=option, amount=amount)
                        except ValueError as exc:
                            await websocket.send_json({"type": "error", "message": str(exc)})
                            continue
                        await self.broadcast_all_states()
                    elif msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
            except WebSocketDisconnect:
                pass
            finally:
                await self._disconnect(token, websocket)

        @app.on_event("startup")
        async def startup() -> None:
            self._shutdown.clear()
            self._clock_task = asyncio.create_task(self._clock_loop())

        @app.on_event("shutdown")
        async def shutdown() -> None:
            self._shutdown.set()
            if self._clock_task is not None:
                await self._clock_task

        self.app = app

    async def _clock_loop(self) -> None:
        while not self._shutdown.is_set():
            await asyncio.sleep(self.tick_rate_seconds)
            async with self.lock:
                self.engine.advance_clock()
            await self.broadcast_all_states()

    async def _disconnect(self, token: str, websocket: WebSocket) -> None:
        async with self.lock:
            sockets = self.connections.get(token)
            if sockets and websocket in sockets:
                sockets.remove(websocket)
            if sockets is not None and not sockets:
                self.connections.pop(token, None)

    async def broadcast_all_states(self) -> None:
        async with self.lock:
            recipients = [(token, set(sockets)) for token, sockets in self.connections.items()]
            payloads = {
                token: {"type": "state", "payload": self.engine.public_state_for(token)}
                for token, _ in recipients
            }

        for token, sockets in recipients:
            dead: list[WebSocket] = []
            for socket in sockets:
                try:
                    await socket.send_json(payloads[token])
                except Exception:
                    dead.append(socket)
            if dead:
                async with self.lock:
                    token_sockets = self.connections.get(token, set())
                    for socket in dead:
                        token_sockets.discard(socket)
                    if not token_sockets:
                        self.connections.pop(token, None)


def create_app(
    *,
    seed: int = 2026,
    lobby_seconds: int = 30,
    starting_bankroll: int = 1_000,
    round_stipend: int = 100,
) -> FastAPI:
    engine = GameEngine(
        seed=seed,
        lobby_seconds=lobby_seconds,
        starting_bankroll=starting_bankroll,
        round_stipend=round_stipend,
    )
    server = GameServer(engine)
    return server.app
