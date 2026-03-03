from __future__ import annotations

import random

from gt_market_making.models import Card
from gt_market_making.scenarios import Scenario3SpreadSuits, Scenario4SumRanks, Scenario7NumberPairs


def test_scenario3_settlement_formula() -> None:
    scenario = Scenario3SpreadSuits(random.Random(1))
    scenario.draws_a = [Card(rank="A", suit="HEART")] * 5 + [Card(rank="A", suit="CLUB")] * 5
    scenario.draws_b = [Card(rank="A", suit="SPADE")] * 10

    settlements = scenario.settlement_prices()

    assert settlements["SUMSUITSA"] == 200
    assert settlements["SUMSUITSB"] == 200
    assert settlements["SPREADSUITAB"] == 500


def test_scenario4_settlement_formula() -> None:
    scenario = Scenario4SumRanks(random.Random(2))
    scenario.draws_a = [Card(rank="7", suit="HEART")] * 5 + [Card(rank="K", suit="CLUB")] * 5
    scenario.draws_b = [Card(rank="A", suit="SPADE")] * 10

    settlements = scenario.settlement_prices()

    assert settlements["SUMRANKA"] == 100
    assert settlements["SUMRANKB"] == 10
    assert settlements["SPREADRANKAB"] == 1090


def test_scenario7_pairs_example_from_packet() -> None:
    scenario = Scenario7NumberPairs(random.Random(3))
    scenario.draws = (
        [Card(rank="2", suit="HEART")] * 3
        + [Card(rank="J", suit="SPADE")] * 4
        + [Card(rank="5", suit="CLUB")] * 2
        + [Card(rank="A", suit="DIAMOND")]
    )

    settlements = scenario.settlement_prices()

    assert settlements["NUMPAIRS"] == 600
