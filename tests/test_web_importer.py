from pathlib import Path

import pytest
import requests

from reputation_monitor.web_importer import (
    NoReviewsFoundError,
    SelectorConfig,
    UnsupportedReviewFormatError,
    WebsiteAccessBlockedError,
    WebsiteImportError,
    fetch_reviews,
    parse_reviews_html,
    validate_public_url,
)


FIXTURE = Path(__file__).parent / "fixtures/supported_reviews.html"
JSON_LD_FIXTURE = Path(__file__).parent / "fixtures/schema_json_ld_reviews.html"
MICRODATA_FIXTURE = Path(__file__).parent / "fixtures/schema_microdata_reviews.html"
CUSTOM_FIXTURE = Path(__file__).parent / "fixtures/custom_selector_reviews.html"
INCOMPLETE_FIXTURE = Path(__file__).parent / "fixtures/incomplete_json_ld_review.html"
UNSUPPORTED_FIXTURE = Path(__file__).parent / "fixtures/unsupported_review_layout.html"
NO_REVIEWS_FIXTURE = Path(__file__).parent / "fixtures/no_reviews.html"
PUBLIC_RESOLVER = lambda hostname: {"93.184.216.34"}


class FakeResponse:
    def __init__(self, status=200, text="", headers=None):
        self.status_code = status
        self.text = text
        self.content = text.encode()
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.is_redirect = status in {301, 302, 303, 307, 308}
        self.is_permanent_redirect = status in {301, 308}


class FakeSession:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error

    def get(self, *args, **kwargs):
        if self.error:
            raise self.error
        return self.responses.pop(0)


def test_parses_supported_fixture_and_resolves_source_url():
    result = parse_reviews_html(FIXTURE.read_text(), "https://example.com/reviews")

    assert len(result.reviews) == 2
    assert result.reviews[0].rating == 2
    assert result.reviews[0].source_label == "https://example.com/reviews/web-001"
    assert result.detected_format == "article.review HTML"
    assert result.issues == []


def test_parses_schema_review_json_ld_and_reports_format():
    result = parse_reviews_html(JSON_LD_FIXTURE.read_text(), "https://example.com/reviews")

    assert result.detected_format == "Schema.org Review JSON-LD"
    assert result.reviews[0].review_id == "https://example.com/reviews/json-001"
    assert result.reviews[0].review_date.isoformat() == "2026-10-15"
    assert result.reviews[0].rating == 2


def test_json_ld_review_inherits_nested_practice():
    html = """<script type="application/ld+json">{
      "@context": "https://schema.org",
      "@type": "MedicalClinic",
      "@id": "https://example.com/practices/nested",
      "name": "Clinique Exemple Nested",
      "review": [{
        "@type": "Review",
        "datePublished": "2026-10-17",
        "reviewRating": {"ratingValue": 5},
        "reviewBody": "A complete nested review."
      }]
    }</script>"""

    result = parse_reviews_html(html, "https://example.com/reviews")

    assert result.reviews[0].practice_name == "Clinique Exemple Nested"
    assert result.reviews[0].practice_id == "https://example.com/practices/nested"


def test_parses_schema_review_microdata_and_reports_format():
    result = parse_reviews_html(MICRODATA_FIXTURE.read_text(), "https://example.com/reviews")

    assert result.detected_format == "Schema.org Review Microdata"
    assert result.reviews[0].practice_name == "Clinique Exemple Rivoli"
    assert result.reviews[0].rating == 4


def test_parses_configured_css_selectors():
    config = SelectorConfig(
        container=".testimonial-card",
        review_text=".comment",
        rating=".score",
        review_date=".published",
        practice_name=".clinic-title",
        review_id=":scope",
        practice_id=":scope",
        source_url=".permalink",
        rating_attribute="aria-label",
        review_id_attribute="data-id",
        practice_id_attribute="data-practice",
    )

    result = parse_reviews_html(
        CUSTOM_FIXTURE.read_text(), "https://example.com/testimonials", config
    )

    assert result.detected_format == "Configured CSS selectors"
    assert result.reviews[0].review_id == "custom-001"
    assert result.reviews[0].practice_id == "practice-rivoli"
    assert result.reviews[0].rating == 3
    assert result.reviews[0].source_label == "https://example.com/reviews/custom-001"


def test_missing_rating_and_date_are_not_defaulted():
    result = parse_reviews_html(INCOMPLETE_FIXTURE.read_text(), "https://example.com/reviews")

    assert result.detected_format == "Schema.org Review JSON-LD"
    assert result.reviews == []
    assert "review_date" in result.issues[0].message
    assert "rating" in result.issues[0].message


@pytest.mark.parametrize(
    "url",
    ["not-a-url", "file:///tmp/reviews.html", "http://localhost/reviews"],
)
def test_rejects_invalid_or_local_urls(url):
    with pytest.raises(WebsiteImportError):
        validate_public_url(url, PUBLIC_RESOLVER)


def test_rejects_private_resolved_destination():
    with pytest.raises(WebsiteAccessBlockedError, match="private"):
        validate_public_url("https://example.com/reviews", lambda hostname: {"10.0.0.8"})


def test_blocks_restricted_google_review_surface_before_request():
    with pytest.raises(WebsiteAccessBlockedError, match="Google"):
        validate_public_url("https://www.google.com/maps/place/example", PUBLIC_RESOLVER)


def test_revalidates_and_blocks_private_redirect():
    session = FakeSession([FakeResponse(302, headers={"Location": "http://127.0.0.1/private"})])
    with pytest.raises(WebsiteImportError, match="private"):
        fetch_reviews(
            "https://example.com/reviews",
            session=session,
            resolver=lambda hostname: {"127.0.0.1"} if hostname == "127.0.0.1" else {"93.184.216.34"},
            check_robots=False,
        )


@pytest.mark.parametrize(
    ("error", "message"),
    [(requests.Timeout(), "timed out"), (requests.ConnectionError(), "failed")],
)
def test_reports_network_errors(error, message):
    with pytest.raises(WebsiteImportError, match=message):
        fetch_reviews(
            "https://example.com/reviews",
            session=FakeSession(error=error),
            resolver=PUBLIC_RESOLVER,
            check_robots=False,
        )


def test_reports_http_error():
    with pytest.raises(WebsiteImportError, match="HTTP 503"):
        fetch_reviews(
            "https://example.com/reviews",
            session=FakeSession([FakeResponse(503)]),
            resolver=PUBLIC_RESOLVER,
            check_robots=False,
        )


def test_distinguishes_blocked_http_access():
    with pytest.raises(WebsiteAccessBlockedError, match="blocked or rate-limited"):
        fetch_reviews(
            "https://example.com/reviews",
            session=FakeSession([FakeResponse(403)]),
            resolver=PUBLIC_RESOLVER,
            check_robots=False,
        )


def test_fetch_returns_detected_format():
    result = fetch_reviews(
        "https://example.com/reviews",
        session=FakeSession([FakeResponse(text=JSON_LD_FIXTURE.read_text())]),
        resolver=PUBLIC_RESOLVER,
        check_robots=False,
    )

    assert result.detected_format == "Schema.org Review JSON-LD"


def test_rejects_unsupported_page_structure():
    with pytest.raises(UnsupportedReviewFormatError, match="does not match"):
        parse_reviews_html(UNSUPPORTED_FIXTURE.read_text(), "https://example.com")


def test_distinguishes_page_without_reviews():
    with pytest.raises(NoReviewsFoundError, match="no review records"):
        parse_reviews_html(NO_REVIEWS_FIXTURE.read_text(), "https://example.com")


def test_fetch_respects_robots_disallow():
    session = FakeSession([FakeResponse(text="User-agent: *\nDisallow: /reviews")])
    with pytest.raises(WebsiteAccessBlockedError, match="robots.txt"):
        fetch_reviews(
            "https://example.com/reviews",
            session=session,
            resolver=PUBLIC_RESOLVER,
        )
