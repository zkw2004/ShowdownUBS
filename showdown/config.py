from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Config:
    open_raise_high_min_number: int = 11
    open_raise_mid_min_number: int = 8
    complete_call_min_number: int = 1
    big_blind_iso_raise_min_number: int = 10
    big_blind_reraise_min_number: int = 12
    big_blind_call_min_number: int = 8
    big_blind_defend_min_number: int = 5
    small_preflop_raise_cap_bb: float = 4.0
    max_preflop_commit_fraction: float = 0.15
    max_normal_commit_fraction: float = 0.40
    short_stack_threshold: int = 60
    short_stack_tighten: float = 0.10
    protect_lead_after_hand: int = 75
    protect_lead_chip_delta: int = 25
    protect_lead_tighten: float = 0.08
    protect_lead_max_commit_fraction: float = 0.20
    chase_after_hand: int = 90
    chase_if_below_delta: int = 10
    chase_loosen: float = 0.07
    call_equity_margin: float = 0.05
    value_raise_margin: float = 0.20
    high_value_equity: float = 0.70
    medium_value_equity: float = 0.55
    check_band_equity: float = 0.35
    strong_raise_equity: float = 0.75
    all_in_equity_threshold: float = 0.60
    all_in_pot_odds_threshold: float = 0.30
    low_equity_bluff_threshold: float = 0.35
    bluff_frequency: float = 0.15
    bluff_bet_fraction: float = 0.50
    bluff_max_stack_fraction: float = 0.25
    pair_bet_fraction: float = 0.70
    strong_value_bet_fraction: float = 0.60
    medium_value_bet_fraction: float = 0.40
    pair_raise_multiplier: float = 2.8
    value_raise_multiplier: float = 2.5
    preflop_reraise_multiplier: float = 2.5
    default_open_raise_to_bb: float = 3.0
    medium_open_raise_to_bb: float = 2.5
    # v6 range-aware defence knobs.
    preflop_value_reraise_equity: float = 0.75
    postflop_value_raise_equity: float = 0.80
    risk_extra_margin: float = 0.20
    raise_range_decay: float = 0.60
    min_range_fraction: float = 0.15
    bet_range_base: float = 0.30
    bet_range_aggro_weight: float = 0.70
    bluff_max_opponent_aggro: float = 0.30
    button_complete_min_percentile: float = 0.16


@dataclass(frozen=True)
class RuleConfig:
    open_raise_min_percentile: float = 0.55
    value_bet_min_equity: float = 0.64
    bet_size_pot_fraction: float = 0.85
    bluff_frequency: float = 0.18
    call_equity_margin: float = 0.04
    max_commitment_fraction: float = 0.45


@dataclass(frozen=True)
class Phase2Config:
    default: RuleConfig = RuleConfig()
    per_rule: dict[str, RuleConfig] | None = None
    unknown_mode: RuleConfig = RuleConfig(
        open_raise_min_percentile=0.85,
        value_bet_min_equity=0.90,
        bet_size_pot_fraction=0.50,
        bluff_frequency=0.0,
        call_equity_margin=0.0,
        max_commitment_fraction=0.15,
    )
    recon_mode: bool = False
    target_delta: int = 25
    hands_per_leg: int = 40

    def for_rule(self, codename: str, solved: bool) -> RuleConfig:
        if not solved:
            return self.unknown_mode
        return (self.per_rule or {}).get(codename, self.default)


@dataclass(frozen=True)
class Phase3Config:
    target_delta: int = 10
    hands_per_leg: int = 60
    seats: int = 6
    # A multiway showdown needs to beat every live number. These offsets make
    # voluntary bets and calls materially tighter than heads-up play.
    extra_call_margin_per_opponent: float = 0.035
    extra_value_equity_per_opponent: float = 0.04


CONFIG = Config()
PHASE2_CONFIG = Phase2Config(recon_mode=os.getenv("SHOWDOWN_RECON_MODE", "").lower() in {"1", "true", "yes"})
PHASE3_CONFIG = Phase3Config()
