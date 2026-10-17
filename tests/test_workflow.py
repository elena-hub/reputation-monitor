from pathlib import Path

import pytest

from reputation_monitor.loader import load_reviews
from reputation_monitor.workflow import run_monitoring


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_current_only_run_reports_metrics_without_new_review_claims():
    current = load_reviews(PROJECT_ROOT / "data/reviews_sample.csv")

    result = run_monitoring(current, maximum_rating=2)

    assert result.average_rating == pytest.approx(11 / 3)
    assert result.rating_distribution == {1: 0, 2: 1, 3: 0, 4: 1, 5: 1}
    assert result.new_reviews is None
    assert result.alerts is None


@pytest.mark.parametrize("threshold", [1, 2, 3, 4, 5])
def test_comparison_thresholds_apply_to_new_reviews(threshold):
    previous = load_reviews(PROJECT_ROOT / "data/reviews_previous.csv")
    current = load_reviews(PROJECT_ROOT / "data/reviews_current.csv")

    result = run_monitoring(current, previous, threshold)

    assert all(review.rating <= threshold for review in result.alerts)
    assert result.new_reviews is not None
    assert len(result.new_reviews) == 3


def test_invalid_threshold_is_rejected():
    current = load_reviews(PROJECT_ROOT / "data/reviews_sample.csv")
    with pytest.raises(ValueError, match="from 1 to 5"):
        run_monitoring(current, maximum_rating=6)
