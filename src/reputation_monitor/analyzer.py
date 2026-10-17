"""Compare validated review snapshots and select alerts."""

from __future__ import annotations

from dataclasses import dataclass

from .loader import Review


@dataclass(frozen=True)
class AnalysisResult:
    """Review groups produced by comparing two snapshots."""

    new_reviews: list[Review]
    new_low_rating_reviews: list[Review]
    all_current_low_rating_reviews: list[Review]


def find_new_reviews(previous: list[Review], current: list[Review]) -> list[Review]:
    """Return current reviews whose stable IDs are absent from the previous set."""

    previous_ids = {review.review_id for review in previous}
    return [review for review in current if review.review_id not in previous_ids]


def find_low_rating_reviews(
    reviews: list[Review], maximum_rating: int = 2
) -> list[Review]:
    """Return reviews at or below the configured rating threshold."""

    if maximum_rating not in range(1, 6):
        raise ValueError("maximum_rating must be from 1 to 5")
    return [review for review in reviews if review.rating <= maximum_rating]


def analyze_reviews(
    previous: list[Review], current: list[Review], maximum_rating: int = 2
) -> AnalysisResult:
    """Find new reviews and the new reviews that should produce alerts."""

    new_reviews = find_new_reviews(previous, current)
    return AnalysisResult(
        new_reviews=new_reviews,
        new_low_rating_reviews=find_low_rating_reviews(new_reviews, maximum_rating),
        all_current_low_rating_reviews=find_low_rating_reviews(current, maximum_rating),
    )
