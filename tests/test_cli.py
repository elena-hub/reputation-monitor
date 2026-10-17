import csv
from argparse import Namespace
from pathlib import Path

import pytest

from reputation_monitor.cli import run


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_cli_generates_reports_and_summary(tmp_path, capsys):
    exit_code = run(
        Namespace(
            previous=PROJECT_ROOT / "data/reviews_previous.csv",
            current=PROJECT_ROOT / "data/reviews_current.csv",
            output_dir=tmp_path,
            maximum_rating=2,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "New reviews:            3" in captured.out
    assert "New low-rating alerts:  2" in captured.out
    assert "Malformed rows skipped: 2" in captured.out
    assert (tmp_path / "alerts.csv").exists()
    assert (tmp_path / "monitoring_report.html").exists()


def test_cli_handles_missing_file(tmp_path, capsys):
    exit_code = run(
        Namespace(
            previous=tmp_path / "missing.csv",
            current=tmp_path / "also-missing.csv",
            output_dir=tmp_path / "reports",
            maximum_rating=2,
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "ERROR:" in captured.err


@pytest.mark.parametrize(
    ("maximum_rating", "expected_ids", "expected_reason", "expected_heading"),
    [
        (1, ["REV-016"], "New review rated 1 star", "New 1-star review alerts"),
        (
            2,
            ["REV-016", "REV-018"],
            "New review rated 1 or 2 stars",
            "New 1- and 2-star review alerts",
        ),
        (
            3,
            ["REV-016", "REV-018"],
            "New review rated 1, 2, or 3 stars",
            "New review alerts for ratings of 1, 2, or 3 stars",
        ),
        (
            5,
            ["REV-016", "REV-017", "REV-018"],
            "New review rated 1, 2, 3, 4, or 5 stars",
            "New review alerts for ratings of 1, 2, 3, 4, or 5 stars",
        ),
    ],
)
def test_cli_keeps_threshold_filtering_and_report_labels_consistent(
    tmp_path,
    capsys,
    maximum_rating,
    expected_ids,
    expected_reason,
    expected_heading,
):
    exit_code = run(
        Namespace(
            previous=PROJECT_ROOT / "data/reviews_previous.csv",
            current=PROJECT_ROOT / "data/reviews_current.csv",
            output_dir=tmp_path,
            maximum_rating=maximum_rating,
        )
    )

    captured = capsys.readouterr()
    with (tmp_path / "alerts.csv").open(encoding="utf-8", newline="") as csv_file:
        alerts = list(csv.DictReader(csv_file))
    html = (tmp_path / "monitoring_report.html").read_text(encoding="utf-8")

    assert exit_code == 0
    assert [alert["review_id"] for alert in alerts] == expected_ids
    assert {alert["alert_reason"] for alert in alerts} == {expected_reason}
    assert expected_heading in html
    assert f"New low-rating alerts:  {len(expected_ids)}" in captured.out
