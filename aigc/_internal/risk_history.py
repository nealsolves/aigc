"""RiskHistory — advisory utility for tracking risk scores over time."""
from __future__ import annotations

from typing import Union

from aigc._internal.risk_scoring import RiskScore

TRAJECTORY_IMPROVING = "improving"
TRAJECTORY_STABLE = "stable"
TRAJECTORY_DEGRADING = "degrading"


class RiskHistory:
    """Advisory utility for tracking risk scores over time for a named entity.

    Records risk score observations and computes trajectory direction.
    Does not modify enforcement behaviour — advisory only.
    """

    def __init__(
        self,
        entity_id: str,
        *,
        stability_band: float = 0.05,
    ) -> None:
        """
        Args:
            entity_id: Unique identifier for the entity being tracked
                (e.g. ``"policy:planner"`` or a session/workflow ID).
            stability_band: Delta threshold that determines whether a change
                in risk score is meaningful. Changes smaller than this (in
                absolute value) are classified as ``"stable"``. Must be in
                [0.0, 1.0]. Defaults to 0.05.
        """
        if not isinstance(entity_id, str):
            raise TypeError(
                f"entity_id must be a str, got {type(entity_id).__name__}."
            )
        if not entity_id:
            raise ValueError("entity_id must be a non-empty string.")
        if isinstance(stability_band, bool):
            raise TypeError(
                f"stability_band must be a float, got {type(stability_band).__name__}."
            )
        if not 0.0 <= stability_band <= 1.0:
            raise ValueError("stability_band must be in [0.0, 1.0].")
        self._entity_id = entity_id
        self._stability_band = stability_band
        self._scores: list[float] = []

    @property
    def entity_id(self) -> str:
        """Unique identifier for the tracked entity."""
        return self._entity_id

    @property
    def scores(self) -> tuple[float, ...]:
        """Immutable ordered sequence of recorded scores (oldest first)."""
        return tuple(self._scores)

    @property
    def latest(self) -> float | None:
        """Most recently recorded score, or None if no scores have been recorded."""
        return self._scores[-1] if self._scores else None

    def record(self, score: Union[float, RiskScore]) -> None:
        """Record a risk score observation.

        Accepts a raw float or a ``RiskScore`` instance (extracts ``.score``).
        Booleans are explicitly rejected — ``bool`` is a subclass of ``int``
        and would otherwise slip through silently.
        """
        if isinstance(score, bool):
            raise TypeError(
                f"score must be a float or RiskScore, got {type(score).__name__}."
            )
        if isinstance(score, RiskScore):
            value = score.score
        elif isinstance(score, (int, float)):
            value = float(score)
        else:
            raise TypeError(
                f"score must be a float or RiskScore, got {type(score).__name__}."
            )
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"score must be in [0.0, 1.0], got {value!r}.")
        self._scores.append(value)

    def trajectory(self) -> str:
        """Compute trajectory direction across all recorded scores.

        Compares the first recorded score to the most recently recorded score.
        Returns one of:

        - ``"improving"``  — score has decreased by more than *stability_band*
        - ``"stable"``     — change is within *stability_band*
        - ``"degrading"``  — score has increased by more than *stability_band*

        Raises:
            ValueError: if fewer than 2 scores have been recorded.
        """
        n = len(self._scores)
        if n < 2:
            raise ValueError(
                f"RiskHistory for {self._entity_id!r} has {n} score(s); "
                "need >= 2 to compute trajectory."
            )
        delta = round(self._scores[-1] - self._scores[0], 10)
        if delta < -self._stability_band:
            return TRAJECTORY_IMPROVING
        if delta > self._stability_band:
            return TRAJECTORY_DEGRADING
        return TRAJECTORY_STABLE
