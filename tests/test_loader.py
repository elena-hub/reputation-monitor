import csv

import pytest

from reputation_monitor.loader import load_reviews


FIELDS = [
    "review_id",
    "practice_id",
    "practice_name",
    "review_date",
    "rating",
    "review_text",
    "source_label",
]


def write_csv(path, rows, fields=FIELDS):
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def valid_row(**changes):
    row = {
        "review_id": "REV-100",
        "practice_id": "PR-100",
        "practice_name": "Example Practice",
        "review_date": "2026-10-01",
        "rating": "2",
        "review_text": "Fictional review",
        "source_label": "Test Source",
    }
    row.update(changes)
    return row


def test_loads_a_valid_review(tmp_path):
    csv_path = tmp_path / "reviews.csv"
    write_csv(csv_path, [valid_row()])

    result = load_reviews(csv_path)

    assert len(result.reviews) == 1
    assert result.reviews[0].rating == 2
    assert result.issues == []


@pytest.mark.parametrize(
    ("changes", "expected_message"),
    [
        ({"review_id": ""}, "empty required field"),
        ({"rating": "six"}, "whole number"),
        ({"rating": "6"}, "from 1 to 5"),
        ({"review_date": "01/10/2026"}, "YYYY-MM-DD"),
    ],
)
def test_reports_malformed_rows(tmp_path, changes, expected_message):
    csv_path = tmp_path / "reviews.csv"
    write_csv(csv_path, [valid_row(**changes)])

    result = load_reviews(csv_path)

    assert result.reviews == []
    assert expected_message in result.issues[0].message


def test_reports_duplicate_identifiers(tmp_path):
    csv_path = tmp_path / "reviews.csv"
    write_csv(csv_path, [valid_row(), valid_row(review_text="Duplicate")])

    result = load_reviews(csv_path)

    assert len(result.reviews) == 1
    assert "duplicate review_id" in result.issues[0].message


def test_missing_required_column_raises_error(tmp_path):
    csv_path = tmp_path / "reviews.csv"
    write_csv(csv_path, [], fields=["review_id", "rating"])

    with pytest.raises(ValueError, match="Missing required columns"):
        load_reviews(csv_path)
