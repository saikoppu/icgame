# GT Market Making Exchange Simulation (Scenarios 3/4/7)

This repository implements Section **2 (Market Making Exchange Simulation)** from the Trading at GT case packet, limited to:

- Scenario 3: Spread of Suits
- Scenario 4: Sum of Ranks
- Scenario 7: Number of Pairs

## Implemented Mechanics

- Central limit order book with price-time matching
- Position limit enforcement (`100` contracts including open orders + inventory)
- Taker bot behavior with per-symbol max volume, spread filters, and decay
- 15-minute game timeline with public reveals every 90 seconds (9 reveals)
- Auction at minute `7.5` with one winner and PnL deduction
- Scenario-specific settlement logic and final PnL
- Utility-based scenario score (with one documented formula assumption)

## Run

```bash
python3 -m pip install -e .
gt-mm-sim --scenarios 3,4,7 --teams 4 --seed 7
```

JSON output:

```bash
gt-mm-sim --scenarios 3,4,7 --json
```

## Package Layout

- `src/gt_market_making/scenarios.py`: scenario generation, reveals, settlement, fair values, bounds
- `src/gt_market_making/exchange.py`: order book and matching engine
- `src/gt_market_making/taker_bot.py`: taker bot execution logic
- `src/gt_market_making/simulator.py`: timeline orchestration, auction, scoring, reports
- `src/gt_market_making/strategies.py`: pluggable team strategies + default market maker
- `src/gt_market_making/cli.py`: command line interface

## Formula Assumption

The PDF text extraction dropped a symbol in the score formula. This implementation uses:

- `U(x) = ln(1 + 35*x/C)` for `x >= 0`
- `U(x) = 35*x/C` for `x < 0`

where `x` is team PnL and `C` is taker bot loss amount.

## Multiplayer Bet Sizing Game (100+ Players)

This repo also includes a realtime multiplayer web game for probabilistic betting competitions:

- 12 escalating probability events (shared random outcome for all players each round)
- 5 GT-based Fermi finals questions after betting rounds
- Event probabilities are hidden from players (they infer/calculate themselves)
- Realtime websocket updates (bankroll, PnL, rankings, timer)
- Admin-only game start
- Join code gate for players
- Auto bust reset: players who hit `$0` are reset to `$500` so everyone can keep playing
- Full leaderboard visible to all users (rank 1 to rank N)
- Built-in admin pane for controlling timers, events, lifecycle, and full leaderboard/results

### Run the server

```bash
python3 -m pip install -e .
bet-sizing-server \
  --host 0.0.0.0 \
  --port 8000 \
  --seed 2026 \
  --admin-key "change-this" \
  --access-code "quant" \
  --starting-bankroll 1000 \
  --bust-rebuy-amount 500 \
  --round-stipend 0
```

Open `http://localhost:8000` from multiple browsers/devices.
Open the `Admin` tab in the app and enter the same admin key.

### Game runtime options

```bash
bet-sizing-server \
  --host 0.0.0.0 \
  --port 8000 \
  --lobby-seconds 30 \
  --starting-bankroll 1000 \
  --bust-rebuy-amount 500 \
  --round-stipend 0 \
  --access-code "quant" \
  --admin-key "change-this"
```

### Docker hosting (single instance)

```bash
docker build -t bet-sizing-game .
docker run --rm -p 8000:8000 bet-sizing-game \
  bet-sizing-server --host 0.0.0.0 --port 8000 \
  --admin-key "change-this" --access-code "quant" \
  --starting-bankroll 1000 --bust-rebuy-amount 500 --round-stipend 0
```

This single-instance websocket server is suitable for 100+ concurrent players on a modest VM/container.
