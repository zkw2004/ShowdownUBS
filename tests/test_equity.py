from showdown.equity import heterogeneous_pot_share, post_reveal_equity, pot_share_vs_ranges, pre_reveal_equity, top_numbers


def test_post_reveal_pair_is_unbeatable() -> None:
    for number in range(1, 14):
        win, tie, lose = post_reveal_equity(number, number)
        assert win == 12 / 13
        assert tie == 1 / 13
        assert lose == 0.0


def test_post_reveal_probabilities_sum_to_one() -> None:
    for my_number in range(1, 14):
        for community in range(1, 14):
            total = sum(post_reveal_equity(my_number, community))
            assert abs(total - 1.0) < 1e-9


def test_pre_reveal_matches_bruteforce_for_thirteen() -> None:
    win, tie, lose = pre_reveal_equity(13)
    assert abs(win - (144 / 169)) < 1e-9
    assert abs(tie - (13 / 169)) < 1e-9
    assert abs(lose - (12 / 169)) < 1e-9


def test_pre_reveal_monotonic_in_number() -> None:
    equities = [pre_reveal_equity(number)[0] + pre_reveal_equity(number)[1] / 2 for number in range(1, 14)]
    assert equities == sorted(equities)


def test_heterogeneous_share_is_the_product_of_independent_ranges() -> None:
    certain = heterogeneous_pot_share(((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)))
    assert certain == 1.0
    coinflips = heterogeneous_pot_share(((0.5, 0.0, 0.5), (0.5, 0.0, 0.5)))
    assert abs(coinflips - 0.25) < 1e-9


def test_a_caller_range_is_wider_than_a_raiser_range() -> None:
    raiser = top_numbers("standard", 0.30)
    caller = tuple(range(1, 14))
    vs_two_raisers = pot_share_vs_ranges(9, None, "standard", (raiser, raiser))
    vs_raiser_and_caller = pot_share_vs_ranges(9, None, "standard", (raiser, caller))
    assert vs_raiser_and_caller > vs_two_raisers
