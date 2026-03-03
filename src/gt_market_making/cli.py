from __future__ import annotations

import argparse
from typing import List

from .simulator import MarketMakingSimulation
from .strategies import SimpleMarketMaker, SimpleMarketMakerConfig
from .taker_bot import TakerBotConfig


def parse_scenarios(raw: str) -> List[int]:
    values = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        scenario_id = int(token)
        if scenario_id not in {3, 4, 7}:
            raise ValueError(f"Unsupported scenario: {scenario_id}. Only 3, 4, and 7 are implemented.")
        values.append(scenario_id)
    if not values:
        raise ValueError("No scenarios provided.")
    return values


def make_strategies(team_count: int, base_auction_bid: int) -> list[SimpleMarketMaker]:
    strategies = []
    for i in range(team_count):
        config = SimpleMarketMakerConfig(
            quote_size=5,
            half_spread=max(4.0, 10.0 - i),
            refresh_interval=5,
            inventory_skew=0.3 + 0.05 * i,
            auction_bid=max(0, base_auction_bid - i * 5),
        )
        strategies.append(SimpleMarketMaker(name=f"TEAM_{i+1}", config=config))
    return strategies


def main() -> None:
    parser = argparse.ArgumentParser(description="GT Market Making Simulation (scenarios 3, 4, 7)")
    parser.add_argument("--scenarios", default="3,4,7", help="Comma-separated scenarios to run (allowed: 3,4,7)")
    parser.add_argument("--teams", type=int, default=4, help="Number of market-making teams")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    parser.add_argument("--auction-bid", type=int, default=60, help="Base auction bid for TEAM_1")
    parser.add_argument("--decision-interval", type=int, default=5, help="Strategy decision interval in seconds")
    parser.add_argument("--max-volume", type=int, default=12, help="Taker bot max volume per symbol per second")
    parser.add_argument("--max-spread", type=float, default=25.0, help="Taker bot max spread around fair value")
    parser.add_argument("--json", action="store_true", help="Print full JSON output")
    args = parser.parse_args()

    scenario_ids = parse_scenarios(args.scenarios)

    for idx, scenario_id in enumerate(scenario_ids):
        strategies = make_strategies(args.teams, args.auction_bid)
        sim = MarketMakingSimulation(
            scenario_id=scenario_id,
            strategies=strategies,
            seed=args.seed + idx,
            decision_interval_seconds=args.decision_interval,
            taker_bot_config=TakerBotConfig(max_volume=args.max_volume, max_spread=args.max_spread),
        )
        report = sim.run()

        if args.json:
            print(report.to_json())
            continue

        print(f"Scenario {report.scenario_id}: {report.scenario_name} (seed={report.seed})")
        print(f"Settlements: {report.settlements}")
        if report.auction:
            print(f"Auction winner: {report.auction.winner} @ {report.auction.winning_bid}")
        print(f"Trades: {report.trade_count}, BotPnL: {report.bot_pnl:.2f}")
        for rank, team in enumerate(report.teams, start=1):
            print(
                f"  {rank}. {team.team} pnl={team.pnl:.2f} score={team.score:.4f} "
                f"auction_paid={team.auction_paid} positions={team.positions}"
            )
        print()


if __name__ == "__main__":
    main()
