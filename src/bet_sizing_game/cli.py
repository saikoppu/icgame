from __future__ import annotations

import argparse

import uvicorn

from .server import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the multiplayer bet sizing game server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface")
    parser.add_argument("--port", type=int, default=8000, help="Port")
    parser.add_argument("--seed", type=int, default=2026, help="Random seed for event outcomes")
    parser.add_argument("--lobby-seconds", type=int, default=30, help="Lobby countdown before round 1 starts")
    parser.add_argument("--starting-bankroll", type=int, default=1000, help="Starting bankroll for each player")
    parser.add_argument("--round-stipend", type=int, default=0, help="Cash injected at the start of each event")
    parser.add_argument(
        "--admin-key",
        default="change-me-admin-key",
        help="Shared secret required for /api/admin/* endpoints",
    )
    args = parser.parse_args()

    app = create_app(
        seed=args.seed,
        lobby_seconds=args.lobby_seconds,
        starting_bankroll=args.starting_bankroll,
        round_stipend=args.round_stipend,
        admin_key=args.admin_key,
    )

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
