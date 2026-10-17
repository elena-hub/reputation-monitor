import csv
from datetime import date, datetime, timezone

from reputation_monitor.analyzer import AnalysisResult
from reputation_monitor.loader import Review, ValidationIssue
from reputation_monitor.reporter import render_html_report, write_alerts_csv, write_html_report


def unsafe_review():
    return Review(
        review_id="REV-<1>",
        practice_id="PR-001",
        practice_name="Example & Practice",
        review_date=date(2026, 10, 1),
        rating=1,
        review_text='<script>alert("unsafe")</script>',
        source_label="Test Source",
    )


def analysis():
    item = unsafe_review()
    return AnalysisResult([item], [item], [item])


def test_writes_alert_csv(tmp_path):
    output_path = tmp_path / "alerts.csv"
    write_alerts_csv([unsafe_review()], output_path)

    with output_path.open(encoding="utf-8", newline="") as csv_file:
        rows = list(csv.DictReader(csv_file))

    assert rows[0]["review_id"] == "REV-<1>"
    assert rows[0]["alert_reason"] == "New review rated 1 or 2 stars"


def test_html_report_escapes_review_content(tmp_path):
    output_path = tmp_path / "report.html"
    write_html_report(
        analysis=analysis(),
        previous_count=0,
        current_count=1,
        previous_issues=[],
        current_issues=[ValidationIssue(3, "unsafe <value>")],
        output_path=output_path,
        generated_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
    )

    html = output_path.read_text(encoding="utf-8")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "unsafe &lt;value&gt;" in html


def test_current_only_report_does_not_claim_reviews_are_new():
    html = render_html_report(
        analysis=None,
        previous_count=None,
        current_count=1,
        previous_issues=[],
        current_issues=[],
        generated_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
    )

    assert "Snapshot comparison not run" in html
    assert "no reviews are identified as new" in html
    assert "New 1- and 2-star review alerts" not in html
