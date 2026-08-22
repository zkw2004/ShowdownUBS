from showdown.evaluator.registry import get_rule


def test_pair_beats_non_pair() -> None:
    rule = get_rule("standard")
    assert rule.rank(5, 5) > rule.rank(13, 7)


def test_higher_number_wins_without_pair() -> None:
    rule = get_rule("standard")
    assert rule.rank(13, 7) > rule.rank(12, 7)


def test_identical_results_tie() -> None:
    rule = get_rule("standard")
    assert rule.rank(9, 3) == rule.rank(9, 3)


def test_rank_handles_no_community() -> None:
    rule = get_rule("standard")
    for number in range(1, 14):
        assert rule.rank(number, None) == (0, number)
