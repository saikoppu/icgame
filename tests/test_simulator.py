from __future__ import annotations

from gt_market_making.simulator import MarketMakingSimulation
from gt_market_making.strategies import SimpleMarketMaker, SimpleMarketMakerConfig


def test_simulation_runs_scenario_3() -> None:
    strategies = [
        SimpleMarketMaker("TEAM_A", SimpleMarketMakerConfig(auction_bid=40)),
        SimpleMarketMaker("TEAM_B", SimpleMarketMakerConfig(auction_bid=20)),
    ]

    sim = MarketMakingSimulation(scenario_id=3, strategies=strategies, seed=11, decision_interval_seconds=10)
    report = sim.run()

    assert report.scenario_id == 3
    assert set(report.settlements) == {"SUMSUITSA", "SUMSUITSB", "SPREADSUITAB"}
    assert len(report.public_reveals["SUMSUITSA"]) == 9
    assert report.auction is not None
    assert report.auction.winner in {"TEAM_A", "TEAM_B"}
    assert report.trade_count >= 0
    assert len(report.teams) == 2
