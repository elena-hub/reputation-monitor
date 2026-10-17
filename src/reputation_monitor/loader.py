"""Load and validate review records from CSV files."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterable, Mapping, TextIO


REQUIRED_FIELDS = (
    "review_id",
    "practice_id",
    "practice_name",
    "review_date",
    "rating",
    "review_text",
    "source_label",
)


@dataclass(frozen=True)
class Review:
    """A validated review from one CSV row."""

    review_id: str
    practice_id: str
    practice_name: str
    review_date: date
    rating: int
    review_text: str
    source_label: str


@dataclass(frozen=True)
class ValidationIssue:
    """A human-readable problem associated with a CSV row."""

    row_number: int
    message: str


@dataclass(frozen=True)
class LoadResult:
    """The valid reviews and invalid-row issues found in one file."""

    reviews: list[Review]
    issues: list[ValidationIssue]


def _validate_headers(fieldnames: list[str] | None) -> None:
    """Raise ValueError when one or more required CSV columns are absent."""

    actual_fields = set(fieldnames or [])
    missing_fields = [field for field in REQUIRED_FIELDS if field not in actual_fields]
    if missing_fields:
        raise ValueError(f"Missing required columns: {', '.join(missing_fields)}")


def parse_review_record(row: Mapping[str, str | None], row_number: int) -> Review:
    """Convert one CSV row into a Review or raise ValueError."""

    values = {field: (row.get(field) or "").strip() for field in REQUIRED_FIELDS}
    empty_fields = [field for field, value in values.items() if not value]
    if empty_fields:
        raise ValueError(f"empty required field(s): {', '.join(empty_fields)}")

    try:
        rating = int(values["rating"])
    except ValueError as error:
        raise ValueError("rating must be a whole number from 1 to 5") from error
    if rating not in range(1, 6):
        raise ValueError("rating must be from 1 to 5")

    try:
        review_date = date.fromisoformat(values["review_date"])
    except ValueError as error:
        raise ValueError("review_date must use YYYY-MM-DD format") from error

    return Review(
        review_id=values["review_id"],
        practice_id=values["practice_id"],
        practice_name=values["practice_name"],
        review_date=review_date,
        rating=rating,
        review_text=values["review_text"],
        source_label=values["source_label"],
    )


def load_review_rows(rows: Iterable[Mapping[str, str | None]]) -> LoadResult:
    """Validate mappings, keeping valid records and describing malformed ones."""
    reviews: list[Review] = []
    issues: list[ValidationIssue] = []
    seen_review_ids: set[str] = set()

    for row_number, row in enumerate(rows, start=2):
        try:
            review = parse_review_record(row, row_number)
            if review.review_id in seen_review_ids:
                raise ValueError(f"duplicate review_id '{review.review_id}' in this input")
            seen_review_ids.add(review.review_id)
            reviews.append(review)
        except ValueError as error:
            issues.append(ValidationIssue(row_number, str(error)))

    return LoadResult(reviews=reviews, issues=issues)


def load_reviews_stream(csv_file: TextIO) -> LoadResult:
    """Read and validate review records from an open text stream."""

    reader = csv.DictReader(csv_file)
    _validate_headers(reader.fieldnames)
    return load_review_rows(reader)


def load_reviews(csv_path: Path) -> LoadResult:
    """Read a UTF-8 CSV file, keeping valid rows and describing malformed rows."""

    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            return load_reviews_stream(csv_file)
    except UnicodeDecodeError as error:
        raise ValueError(f"File is not valid UTF-8: {csv_path}") from error
