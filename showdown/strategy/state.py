from __future__ import annotations

from dataclasses import dataclass

from showdown.models import Context


@dataclass
class AttemptState:
    last_leg: int | None = None
    last_match_id: str | None = None

    def observe(self, ctx: Context) -> bool:
        """Return whether this request begins a new leg.

        Only leg identity resets here.  The registry intentionally remains global;
        future opponent modelling can be held on this object and carried across legs.
        """
        new_leg = ctx.leg_number is not None and ctx.leg_number != self.last_leg
        if new_leg:
            self.last_leg = ctx.leg_number
        if ctx.match_id is not None:
            self.last_match_id = ctx.match_id
        return new_leg


ATTEMPT_STATE = AttemptState()
