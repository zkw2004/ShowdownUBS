from __future__ import annotations


class StandardRule:
    codename = "standard"

    def rank(self, number: int, community: int | None) -> tuple[int, int]:
        is_pair = community is not None and number == community
        return (1 if is_pair else 0, 0 if is_pair else number)
