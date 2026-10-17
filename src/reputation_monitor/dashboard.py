"""Streamlit dashboard for interactive reputation monitoring."""

from __future__ import annotations

from io import StringIO
import logging
from pathlib import Path
from collections.abc import MutableMapping

import streamlit as st

from .loader import LoadResult, Review, load_reviews_stream
from .reporter import render_alerts_csv, render_html_report
from .web_importer import (
    NoReviewsFoundError,
    SelectorConfig,
    UnsupportedReviewFormatError,
    WebsiteAccessBlockedError,
    WebsiteImportError,
    WebsiteImportResult,
    fetch_reviews,
)
from .workflow import MonitoringRun, run_monitoring


PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGGER = logging.getLogger(__name__)
DEFAULT_MAXIMUM_RATING = 2
RESTRICTED_IMPORT_MESSAGE = (
    "Reviews couldn't be imported from this website.\n\n"
    "This website restricts automated access. You can still analyze your reviews by uploading a CSV file."
)


def format_alert_slider_label(maximum_rating: int) -> str:
    """Describe the selected maximum alert rating in user-facing language."""

    if maximum_rating not in range(1, 6):
        raise ValueError("maximum_rating must be from 1 to 5")
    unit = "star" if maximum_rating == 1 else "stars"
    return f"Alert me about new reviews rated {maximum_rating} {unit} or less"


def switch_to_csv_upload(state: MutableMapping | None = None) -> None:
    """Switch the source widget without changing threshold or other settings."""

    active_state = st.session_state if state is None else state
    active_state["import_method"] = "CSV upload"


def _show_csv_alternative(message: str) -> None:
    """Show a non-technical website-import outcome and its CSV recovery action."""

    st.error(message)
    st.button("Switch to CSV Upload", on_click=switch_to_csv_upload)


def load_uploaded_csv(uploaded_file) -> LoadResult:
    """Decode and validate a Streamlit CSV upload."""

    try:
        text = uploaded_file.getvalue().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("The uploaded CSV must use UTF-8 encoding.") from error
    return load_reviews_stream(StringIO(text, newline=""))


def review_rows(reviews: list[Review]) -> list[dict[str, object]]:
    """Convert typed reviews to table rows without changing their values."""

    return [
        {
            "Review ID": review.review_id,
            "Practice": review.practice_name,
            "Date": review.review_date.isoformat(),
            "Rating": review.rating,
            "Review text": review.review_text,
            "Source": review.source_label,
        }
        for review in reviews
    ]


def format_csv_import_status(snapshot: str, result: LoadResult) -> tuple[str, str]:
    """Return the status level and user-facing CSV import summary."""

    if snapshot not in {"current", "previous"}:
        raise ValueError("snapshot must be current or previous")
    imported_count = len(result.reviews)
    rejected_count = len(result.issues)
    if snapshot == "current":
        ready_text = f"{imported_count} reviews ready for analysis"
        success_text = f"Current reviews imported successfully — {ready_text}."
        subject = "Current reviews"
    else:
        ready_text = f"{imported_count} reviews available for comparison"
        success_text = f"Previous reviews imported successfully — {ready_text}."
        subject = "Previous reviews"
    if rejected_count == 0:
        return "success", success_text
    rejected_label = "review" if rejected_count == 1 else "reviews"
    verb = "couldn't be imported" if imported_count == 0 else "imported with issues"
    return (
        "error" if imported_count == 0 else "warning",
        f"{subject} {verb} — {ready_text}; {rejected_count} {rejected_label} rejected "
        "because required information was missing, invalid, or duplicated.",
    )


def _log_rejected_reviews(label: str, result: LoadResult) -> None:
    for issue in result.issues:
        LOGGER.warning(
            "%s record rejected at source row %s: %s",
            label,
            issue.row_number,
            issue.message,
        )


def _show_csv_import_status(snapshot: str, result: LoadResult | None) -> None:
    if result is None:
        return
    level, message = format_csv_import_status(snapshot, result)
    getattr(st, level)(message)
    _log_rejected_reviews(f"{snapshot.title()} CSV", result)


def _show_website_import_status(result: LoadResult) -> None:
    imported_count = len(result.reviews)
    rejected_count = len(result.issues)
    if rejected_count == 0:
        st.success(f"Website reviews extracted successfully — {imported_count} reviews ready for preview.")
        return
    st.warning(
        f"Website extraction completed — {imported_count} reviews ready for preview; "
        f"{rejected_count} reviews rejected because required information was missing or invalid."
    )
    _log_rejected_reviews("Website extraction", result)


def _show_results(run: MonitoringRun) -> None:
    practices = sorted({review.practice_name for review in run.current.reviews})
    st.subheader("Monitoring summary")
    st.caption("Practice: " + (", ".join(practices) if practices else "No valid reviews"))
    columns = st.columns(4)
    columns[0].metric("Current reviews", len(run.current.reviews))
    columns[1].metric(
        "Average rating", f"{run.average_rating:.2f}" if run.average_rating is not None else "—"
    )
    columns[2].metric("New reviews", len(run.new_reviews) if run.new_reviews is not None else "Not calculated")
    columns[3].metric("New alerts", len(run.alerts) if run.alerts is not None else "Not calculated")

    st.subheader("Rating distribution")
    st.bar_chart({"Reviews": run.rating_distribution})

    if run.analysis is None:
        st.info(
            "No previous snapshot was supplied. Current metrics are shown, but the app does not identify reviews as new or create new-review alerts."
        )
    else:
        st.subheader("New low-rating alerts")
        st.dataframe(review_rows(run.alerts or []), use_container_width=True)

    st.subheader("Current review details")
    st.dataframe(review_rows(run.current.reviews), use_container_width=True)
    _show_csv_import_status("current", run.current)
    _show_csv_import_status("previous", run.previous)

    previous_count = len(run.previous.reviews) if run.previous is not None else None
    previous_issues = run.previous.issues if run.previous is not None else []
    html_report = render_html_report(
        run.analysis,
        previous_count,
        len(run.current.reviews),
        previous_issues,
        run.current.issues,
        maximum_rating=run.maximum_rating,
    )
    st.download_button(
        "Download HTML report",
        html_report,
        file_name="monitoring_report.html",
        mime="text/html",
    )
    if run.alerts is not None:
        st.download_button(
            "Download CSV alerts",
            render_alerts_csv(run.alerts, run.maximum_rating),
            file_name="alerts.csv",
            mime="text/csv",
        )


def main() -> None:
    """Render the dashboard."""

    st.set_page_config(page_title="Reputation Monitor", page_icon="📊", layout="wide")
    st.title("Reputation Monitor")
    st.write("Analyze authorized review data locally from CSV files or a supported public webpage.")
    selected_threshold = st.session_state.get("maximum_rating", DEFAULT_MAXIMUM_RATING)
    threshold = st.slider(
        format_alert_slider_label(selected_threshold),
        1,
        5,
        DEFAULT_MAXIMUM_RATING,
        key="maximum_rating",
    )
    st.caption("Choose which ratings should trigger an alert when new reviews are detected.")
    input_method = st.radio(
        "Import method",
        ["CSV upload", "Import from Website"],
        horizontal=True,
        key="import_method",
    )

    current: LoadResult | None = None
    previous: LoadResult | None = None
    if input_method == "CSV upload":
        sample_path = PROJECT_ROOT / "data" / "reviews_sample.csv"
        if sample_path.exists():
            st.download_button(
                "Download sample CSV",
                sample_path.read_bytes(),
                file_name="reviews_sample.csv",
                mime="text/csv",
            )
        current_upload = st.file_uploader("Current review CSV", type=["csv"])
        previous_upload = st.file_uploader("Previous review CSV (optional)", type=["csv"])
        if current_upload is not None:
            try:
                current = load_uploaded_csv(current_upload)
            except ValueError as error:
                LOGGER.warning("Current CSV import failed", exc_info=True)
                st.error(
                    "Current reviews couldn't be imported — 0 reviews ready for analysis. "
                    "Check that the CSV uses UTF-8 and includes all required columns."
                )
            if current is not None and previous_upload is not None:
                try:
                    previous = load_uploaded_csv(previous_upload)
                except ValueError as error:
                    LOGGER.warning("Previous CSV import failed", exc_info=True)
                    st.error(
                        "Previous reviews couldn't be imported — 0 reviews available for comparison. "
                        "Check that the CSV uses UTF-8 and includes all required columns."
                    )
    else:
        st.subheader("Import from Website")
        st.caption(
            "Use only a public page you are authorized to access. Imports respect robots.txt, block private network destinations and restricted platforms, and do not bypass authentication or anti-bot controls."
        )
        website_url = st.text_input("Public review page URL", placeholder="https://example.com/reviews")
        selector_config = None
        with st.expander("Custom CSS selectors (optional)"):
            use_custom_selectors = st.checkbox("Use selectors for this website layout")
            container_selector = st.text_input("Review container selector", placeholder=".review-card")
            review_text_selector = st.text_input("Review text selector", placeholder=".review-body")
            rating_selector = st.text_input("Rating selector", placeholder=".rating")
            date_selector = st.text_input("Date selector", placeholder="time")
            practice_name_selector = st.text_input("Practice name selector", placeholder=".practice-name")
            review_id_selector = st.text_input("Review ID selector (optional)", placeholder="[data-id]")
            practice_id_selector = st.text_input("Practice ID selector (optional)")
            source_url_selector = st.text_input("Source link selector (optional)", placeholder="a.permalink")
            rating_attribute = st.text_input("Rating attribute", value="data-rating")
            date_attribute = st.text_input("Date attribute", value="datetime")
            review_id_attribute = st.text_input("Review ID attribute (optional)", placeholder="data-id")
            practice_id_attribute = st.text_input("Practice ID attribute (optional)")
        if use_custom_selectors:
            required_selectors = {
                "container": container_selector,
                "review text": review_text_selector,
                "rating": rating_selector,
                "date": date_selector,
                "practice name": practice_name_selector,
            }
            missing_selectors = [name for name, value in required_selectors.items() if not value.strip()]
            if missing_selectors:
                st.warning("Complete these required selectors before importing: " + ", ".join(missing_selectors))
            else:
                selector_config = SelectorConfig(
                    container=container_selector,
                    review_text=review_text_selector,
                    rating=rating_selector,
                    review_date=date_selector,
                    practice_name=practice_name_selector,
                    review_id=review_id_selector,
                    practice_id=practice_id_selector,
                    source_url=source_url_selector,
                    rating_attribute=rating_attribute,
                    date_attribute=date_attribute,
                    review_id_attribute=review_id_attribute,
                    practice_id_attribute=practice_id_attribute,
                )
        if st.button("Import reviews", type="primary") and website_url:
            st.session_state.pop("website_import_result", None)
            st.session_state["website_analysis_ready"] = False
            if use_custom_selectors and selector_config is None:
                st.error("The configured layout is incomplete. Add every required selector.")
            else:
                try:
                    st.session_state["website_import_result"] = fetch_reviews(
                        website_url, selector_config=selector_config
                    )
                except WebsiteAccessBlockedError as error:
                    LOGGER.warning("Website review import was blocked for %s", website_url, exc_info=True)
                    _show_csv_alternative(RESTRICTED_IMPORT_MESSAGE)
                except NoReviewsFoundError as error:
                    LOGGER.info("No reviews were found at %s: %s", website_url, error)
                    _show_csv_alternative(
                        "No reviews were found in the page's accessible HTML. You can configure supported CSS selectors or upload a CSV file."
                    )
                except UnsupportedReviewFormatError as error:
                    LOGGER.info("Unsupported review HTML at %s: %s", website_url, error)
                    _show_csv_alternative(
                        "The page uses an unsupported review format. Configure CSS selectors for this layout or upload a CSV file."
                    )
                except WebsiteImportError as error:
                    LOGGER.warning("Website review import failed for %s", website_url, exc_info=True)
                    _show_csv_alternative(
                        "Reviews couldn't be imported. Check the public page URL or continue by uploading a CSV file."
                    )

        imported: WebsiteImportResult | None = st.session_state.get("website_import_result")
        if imported is not None:
            st.success(f"Detected format: {imported.detected_format}")
            st.subheader("Extracted-record preview")
            st.dataframe(review_rows(imported.reviews), use_container_width=True)
            for notice in imported.notices:
                st.info(notice)
            _show_website_import_status(imported.as_load_result())
            if not imported.reviews:
                st.error(
                    "Review elements were detected, but no complete records can be analyzed. Missing or invalid ratings, dates, practice names, or review text are reported above."
                )
            elif st.button("Analyze previewed reviews"):
                st.session_state["website_analysis_ready"] = True
            if st.session_state.get("website_analysis_ready"):
                current = imported.as_load_result()

    if current is not None:
        _show_results(run_monitoring(current, previous, threshold))


if __name__ == "__main__":
    main()
