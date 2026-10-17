from datetime import date

import pytest

from reputation_monitor.analyzer import analyze_reviews, find_low_rating_reviews
from reputation_monitor.loader import Review


def review(review_id, rating):
    return Review(
        review_id=review_id,
        practice_id="PR-001",
        practice_name="Example Practice",
        review_date=date(2026, 10, 1),
        rating=rating,
        review_text="Fictional review",
        source_label="Test Source",
    )


def test_analysis_reports_only_new_low_ratings_as_alerts():
    previous = [review("REV-001", 1), review("REV-002", 5)]
    current = [review("REV-001", 1), review("REV-002", 5), review("REV-003", 2), review("REV-004", 4)]

    result = analyze_reviews(previous, current)

    assert [item.review_id for item in result.new_reviews] == ["REV-003", "REV-004"]
    assert [item.review_id for item in result.new_low_rating_reviews] == ["REV-003"]
    assert [item.review_id for item in result.all_current_low_rating_reviews] == ["REV-001", "REV-003"]


def test_invalid_threshold_is_rejected():
    with pytest.raises(ValueError, match="from 1 to 5"):
        find_low_rating_reviews([], maximum_rating=0)
