from __future__ import annotations

from typing import Protocol


class ShowdownRule(Protocol):
    codename: str

    def rank(self, number: int, community: int | None) -> tuple[int, int]:
        """Return a comparable ranking tuple where larger is better."""
