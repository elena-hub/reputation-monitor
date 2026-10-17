"""Write machine-readable alerts and a safe HTML monitoring report."""

from __future__ import annotations

import csv
from datetime import datetime
from html import escape
from io import StringIO
from pathlib import Path

from .analyzer import AnalysisResult
from .loader import Review, ValidationIssue


ALERT_FIELDS = (
    "review_id",
    "practice_id",
    "practice_name",
    "review_date",
    "rating",
    "review_text",
    "source_label",
    "alert_reason",
)


def format_rating_threshold(maximum_rating: int) -> str:
    """Return a readable description of ratings from 1 through the threshold."""

    if maximum_rating not in range(1, 6):
        raise ValueError("maximum_rating must be from 1 to 5")
    if maximum_rating == 1:
        return "1 star"
    ratings = [str(rating) for rating in range(1, maximum_rating + 1)]
    if maximum_rating == 2:
        return "1 or 2 stars"
    return f"{', '.join(ratings[:-1])}, or {ratings[-1]} stars"


def _alert_heading(maximum_rating: int) -> str:
    """Return the HTML heading for the configured rating threshold."""

    if maximum_rating == 1:
        return "New 1-star review alerts"
    if maximum_rating == 2:
        return "New 1- and 2-star review alerts"
    return f"New review alerts for ratings of {format_rating_threshold(maximum_rating)}"


def write_alerts_csv(
    alerts: list[Review], output_path: Path, maximum_rating: int = 2
) -> None:
    """Write new low-rating reviews to a CSV file."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_alerts_csv(alerts, maximum_rating), encoding="utf-8", newline=""
    )


def render_alerts_csv(alerts: list[Review], maximum_rating: int = 2) -> str:
    """Return an alerts CSV suitable for a file or Streamlit download."""

    alert_reason = f"New review rated {format_rating_threshold(maximum_rating)}"
    output = StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=ALERT_FIELDS, lineterminator="\n")
    writer.writeheader()
    for review in alerts:
        writer.writerow(
            {
                "review_id": review.review_id,
                "practice_id": review.practice_id,
                "practice_name": review.practice_name,
                "review_date": review.review_date.isoformat(),
                "rating": review.rating,
                "review_text": review.review_text,
                "source_label": review.source_label,
                "alert_reason": alert_reason,
            }
        )
    return output.getvalue()


def _comparison_cards(
    analysis: AnalysisResult | None, previous_count: int | None
) -> str:
    if analysis is None or previous_count is None:
        return '<div class="card"><span class="number">Not run</span>snapshot comparison</div>'
    return (
        f'<div class="card"><span class="number">{previous_count}</span>valid previous reviews</div>'
        f'<div class="card"><span class="number">{len(analysis.new_reviews)}</span>new reviews</div>'
        f'<div class="card"><span class="number">{len(analysis.new_low_rating_reviews)}</span>new alerts</div>'
    )


def _comparison_section(analysis: AnalysisResult | None, maximum_rating: int) -> str:
    if analysis is None:
        return """<section class="notice" aria-labelledby="comparison-heading">
      <h2 id="comparison-heading">Snapshot comparison not run</h2>
      <p>No previous snapshot was supplied. Current-review metrics are available, but no reviews are identified as new and no new-review alerts are generated.</p>
    </section>"""
    return f"""<section aria-labelledby="alerts-heading">
      <h2 id="alerts-heading">{_alert_heading(maximum_rating)}</h2>
      <div class="table-wrap">
        <table>
          <thead><tr><th scope="col">Review ID</th><th scope="col">Practice</th><th scope="col">Date</th><th scope="col">Rating</th><th scope="col">Review text</th><th scope="col">Source</th></tr></thead>
          <tbody>{_alert_rows(analysis.new_low_rating_reviews)}</tbody>
        </table>
      </div>
    </section>"""


def render_html_report(
    analysis: AnalysisResult | None,
    previous_count: int | None,
    current_count: int,
    previous_issues: list[ValidationIssue],
    current_issues: list[ValidationIssue],
    generated_at: datetime | None = None,
    maximum_rating: int = 2,
) -> str:
    """Return a standalone, escaped HTML monitoring report."""

    timestamp = generated_at or datetime.now().astimezone()
    previous_findings = (
        _issue_items("Previous snapshot", previous_issues)
        if previous_count is not None
        else "<li>Previous snapshot: not supplied</li>"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Reputation monitoring report</title>
  <style>
    body {{ color: #17212b; font-family: system-ui, sans-serif; line-height: 1.5; margin: 0 auto; max-width: 1100px; padding: 2rem; }}
    .summary {{ display: grid; gap: 1rem; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }}
    .card {{ background: #f3f6f8; border-left: 4px solid #315b7d; padding: 1rem; }}
    .number {{ display: block; font-size: 1.8rem; font-weight: 700; }}
    .table-wrap {{ overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ccd5dc; padding: .65rem; text-align: left; vertical-align: top; }}
    th {{ background: #e7eef3; }}
    .notice {{ background: #fff6d8; padding: 1rem; }}
  </style>
</head>
<body>
  <main>
    <h1>Reputation monitoring report</h1>
    <p>Generated {escape(timestamp.isoformat(timespec="seconds"))}. Review data is processed locally; this report does not represent live monitoring of any review platform.</p>
    <section aria-labelledby="summary-heading">
      <h2 id="summary-heading">Snapshot summary</h2>
      <div class="summary">
        <div class="card"><span class="number">{current_count}</span>valid current reviews</div>
        {_comparison_cards(analysis, previous_count)}
      </div>
    </section>
    {_comparison_section(analysis, maximum_rating)}
    <section class="notice" aria-labelledby="validation-heading">
      <h2 id="validation-heading">Validation findings</h2>
      <ul>
        {previous_findings}
        {_issue_items("Current snapshot", current_issues)}
      </ul>
    </section>
  </main>
</body>
</html>
"""


def _alert_rows(alerts: list[Review]) -> str:
    if not alerts:
        return '<tr><td colspan="6">No new low-rating reviews.</td></tr>'
    rows = []
    for review in alerts:
        rows.append(
            "<tr>"
            f"<td>{escape(review.review_id)}</td>"
            f"<td>{escape(review.practice_name)}</td>"
            f"<td>{review.review_date.isoformat()}</td>"
            f"<td>{review.rating}</td>"
            f"<td>{escape(review.review_text)}</td>"
            f"<td>{escape(review.source_label)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _issue_items(label: str, issues: list[ValidationIssue]) -> str:
    if not issues:
        return f"<li>{escape(label)}: no validation issues</li>"
    return "\n".join(
        f"<li>{escape(label)}, row {issue.row_number}: {escape(issue.message)}</li>"
        for issue in issues
    )


def write_html_report(
    analysis: AnalysisResult,
    previous_count: int,
    current_count: int,
    previous_issues: list[ValidationIssue],
    current_issues: list[ValidationIssue],
    output_path: Path,
    generated_at: datetime | None = None,
    maximum_rating: int = 2,
) -> None:
    """Write a standalone HTML summary, escaping all review-supplied text."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_html_report(
            analysis,
            previous_count,
            current_count,
            previous_issues,
            current_issues,
            generated_at,
            maximum_rating,
        ),
        encoding="utf-8",
    )
