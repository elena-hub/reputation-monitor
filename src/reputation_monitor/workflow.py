"""Shared monitoring workflow for the CLI and Streamlit interface."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean

from .analyzer import AnalysisResult, analyze_reviews
from .loader import LoadResult, Review


@dataclass(frozen=True)
class MonitoringRun:
    """Validated input, metrics, and optional snapshot comparison results."""

    current: LoadResult
    previous: LoadResult | None
    analysis: AnalysisResult | None
    maximum_rating: int
    average_rating: float | None
    rating_distribution: dict[int, int]

    @property
    def new_reviews(self) -> list[Review] | None:
        return None if self.analysis is None else self.analysis.new_reviews

    @property
    def alerts(self) -> list[Review] | None:
        return None if self.analysis is None else self.analysis.new_low_rating_reviews


def run_monitoring(
    current: LoadResult,
    previous: LoadResult | None = None,
    maximum_rating: int = 2,
) -> MonitoringRun:
    """Calculate current metrics and compare snapshots when previous data exists."""

    if maximum_rating not in range(1, 6):
        raise ValueError("maximum_rating must be from 1 to 5")
    ratings = [review.rating for review in current.reviews]
    distribution = {rating: ratings.count(rating) for rating in range(1, 6)}
    analysis = (
        analyze_reviews(previous.reviews, current.reviews, maximum_rating)
        if previous is not None
        else None
    )
    return MonitoringRun(
        current=current,
        previous=previous,
        analysis=analysis,
        maximum_rating=maximum_rating,
        average_rating=fmean(ratings) if ratings else None,
        rating_distribution=distribution,
    )
