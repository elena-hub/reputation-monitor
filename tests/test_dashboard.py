from types import SimpleNamespace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from reputation_monitor import dashboard
from reputation_monitor.dashboard import (
    DEFAULT_MAXIMUM_RATING,
    RESTRICTED_IMPORT_MESSAGE,
    format_csv_import_status,
    format_alert_slider_label,
    load_uploaded_csv,
    review_rows,
    safe_log_origin,
    switch_to_csv_upload,
)
from reputation_monitor.loader import LoadResult, ValidationIssue
from reputation_monitor.reporter import render_alerts_csv, render_html_report
from reputation_monitor.workflow import run_monitoring


class Upload:
    def __init__(self, data: bytes):
        self.data = data

    def getvalue(self):
        return self.data


VALID_CSV = b"review_id,practice_id,practice_name,review_date,rating,review_text,source_label\nR1,P1,Example Practice,2026-10-17,1,Needs follow-up,Authorized export\n"


def test_csv_upload_and_download_payloads():
    current = load_uploaded_csv(Upload(VALID_CSV))
    run = run_monitoring(current)

    html = render_html_report(None, None, 1, [], current.issues)
    alerts = render_alerts_csv([], 2)

    assert review_rows(current.reviews)[0]["Review ID"] == "R1"
    assert "Snapshot comparison not run" in html
    assert "No previous snapshot was supplied" in html
    assert alerts.startswith("review_id,practice_id")


def test_csv_upload_rejects_invalid_utf8():
    with pytest.raises(ValueError, match="UTF-8"):
        load_uploaded_csv(Upload(b"\xff\xfe"))


def test_current_csv_success_message_reports_imported_count():
    current = load_uploaded_csv(Upload(VALID_CSV))

    assert format_csv_import_status("current", current) == (
        "success",
        "Current reviews imported successfully — 1 reviews ready for analysis.",
    )


def test_previous_csv_success_message_reports_imported_count():
    previous = load_uploaded_csv(Upload(VALID_CSV))

    assert format_csv_import_status("previous", previous) == (
        "success",
        "Previous reviews imported successfully — 1 reviews available for comparison.",
    )


def test_partial_csv_import_reports_imported_and_rejected_counts_without_details():
    current = LoadResult(
        reviews=load_uploaded_csv(Upload(VALID_CSV)).reviews,
        issues=[ValidationIssue(3, "rating must be from 1 to 5")],
    )

    level, message = format_csv_import_status("current", current)

    assert level == "warning"
    assert message == (
        "Current reviews imported with issues — 1 reviews ready for analysis; "
        "1 review rejected because required information was missing, invalid, or duplicated."
    )
    assert "row" not in message
    assert "rating must" not in message


def test_rejected_csv_import_reports_zero_imported_and_rejected_count():
    previous = LoadResult(
        reviews=[],
        issues=[
            ValidationIssue(2, "empty required field(s): review_id"),
            ValidationIssue(3, "rating must be from 1 to 5"),
        ],
    )

    assert format_csv_import_status("previous", previous) == (
        "error",
        "Previous reviews couldn't be imported — 0 reviews available for comparison; "
        "2 reviews rejected because required information was missing, invalid, or duplicated.",
    )


def test_rejected_csv_details_are_written_to_logs(caplog):
    result = LoadResult(
        reviews=[],
        issues=[ValidationIssue(7, "rating must be from 1 to 5")],
    )

    dashboard._log_rejected_reviews("Current CSV", result)

    assert "Current CSV record rejected at source row 7" in caplog.text
    assert "rating must be from 1 to 5" in caplog.text


def test_duplicate_identifier_value_is_not_written_to_logs(caplog):
    result = LoadResult(
        reviews=[],
        issues=[ValidationIssue(9, "duplicate review_id 'private-review-123' in this input")],
    )

    dashboard._log_rejected_reviews("Current CSV", result)

    assert "duplicate review_id in this input" in caplog.text
    assert "private-review-123" not in caplog.text


def test_safe_log_origin_excludes_path_query_and_fragment():
    assert safe_log_origin(
        "https://Example.com/private/path?access_token=secret#review"
    ) == "https://example.com"


@pytest.mark.parametrize(
    ("threshold", "expected_label"),
    [
        (1, "Alert me about new reviews rated 1 star or less"),
        (2, "Alert me about new reviews rated 2 stars or less"),
        (3, "Alert me about new reviews rated 3 stars or less"),
        (4, "Alert me about new reviews rated 4 stars or less"),
        (5, "Alert me about new reviews rated 5 stars or less"),
    ],
)
def test_alert_slider_label_matches_selected_threshold(threshold, expected_label):
    assert format_alert_slider_label(threshold) == expected_label


def test_default_alert_threshold_remains_two_stars():
    assert DEFAULT_MAXIMUM_RATING == 2
    assert format_alert_slider_label(DEFAULT_MAXIMUM_RATING) == (
        "Alert me about new reviews rated 2 stars or less"
    )


def test_streamlit_slider_label_updates_for_all_values():
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "streamlit_app.py").run()

    assert app.slider[0].value == 2
    for threshold in range(1, 6):
        app.slider[0].set_value(threshold).run()
        assert app.slider[0].label == format_alert_slider_label(threshold)
        assert app.slider[0].value == threshold
    assert any(
        caption.value
        == "Choose which ratings should trigger an alert when new reviews are detected."
        for caption in app.caption
    )


def test_restricted_import_message_is_exact_and_non_technical():
    assert RESTRICTED_IMPORT_MESSAGE == (
        "Reviews couldn't be imported from this website.\n\n"
        "This website restricts automated access. You can still analyze your reviews by uploading a CSV file."
    )
    for technical_detail in ("robots.txt", "HTTP", "Traceback", "parser", "exception"):
        assert technical_detail not in RESTRICTED_IMPORT_MESSAGE


def test_switch_to_csv_preserves_threshold_and_other_settings():
    state = {
        "import_method": "Import from Website",
        "maximum_rating": 4,
        "website_url": "https://example.com/reviews",
        "website_import_result": object(),
        "website_analysis_ready": True,
    }

    switch_to_csv_upload(state)

    assert state == {
        "import_method": "CSV upload",
        "maximum_rating": 4,
        "website_url": "https://example.com/reviews",
    }


def test_restricted_message_renders_csv_switch_button(monkeypatch):
    errors = []
    buttons = []
    fake_streamlit = SimpleNamespace(
        session_state={"import_method": "Import from Website", "maximum_rating": 3},
        error=errors.append,
    )

    def click_button(label, on_click):
        buttons.append(label)
        on_click()

    fake_streamlit.button = click_button
    monkeypatch.setattr(dashboard, "st", fake_streamlit)

    dashboard._show_csv_alternative(RESTRICTED_IMPORT_MESSAGE)

    assert errors == [RESTRICTED_IMPORT_MESSAGE]
    assert buttons == ["Switch to CSV Upload"]
    assert fake_streamlit.session_state["import_method"] == "CSV upload"
    assert fake_streamlit.session_state["maximum_rating"] == 3
