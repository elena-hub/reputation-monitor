"""Safely import reviews from supported structured data and HTML layouts."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag
from soupsieve.util import SelectorSyntaxError

from .loader import LoadResult, Review, ValidationIssue, load_review_rows


USER_AGENT = "ReputationMonitor/1.0 (+https://reputation-management-service.com/en/docs/python-reputation-monitoring/)"
MAX_RESPONSE_BYTES = 2_000_000
MAX_REDIRECTS = 3
REQUEST_TIMEOUT = (3.05, 10)


class WebsiteImportError(ValueError):
    """A safe, user-facing website import failure."""


class WebsiteAccessBlockedError(WebsiteImportError):
    """Access was refused by policy, destination checks, or the remote site."""


class NoReviewsFoundError(WebsiteImportError):
    """The accessible page contained no recognizable review records."""


class UnsupportedReviewFormatError(WebsiteImportError):
    """Review-like content exists but does not use a supported format."""


@dataclass(frozen=True)
class SelectorConfig:
    """CSS selectors and optional attributes for one authorized layout."""

    container: str
    review_text: str
    rating: str
    review_date: str
    practice_name: str
    review_id: str = ""
    practice_id: str = ""
    source_url: str = ""
    rating_attribute: str = "data-rating"
    date_attribute: str = "datetime"
    review_id_attribute: str = ""
    practice_id_attribute: str = ""
    source_url_attribute: str = "href"


@dataclass(frozen=True)
class WebsiteImportResult:
    """Validated reviews plus extraction details for preview and analysis."""

    reviews: list[Review]
    issues: list[ValidationIssue]
    detected_format: str
    notices: list[str] = field(default_factory=list)

    def as_load_result(self) -> LoadResult:
        return LoadResult(self.reviews, self.issues)


@dataclass(frozen=True)
class _Extraction:
    rows: list[dict[str, str]]
    notices: list[str] = field(default_factory=list)


def _default_resolver(hostname: str) -> set[str]:
    return {item[4][0] for item in socket.getaddrinfo(hostname, None)}


def _is_restricted_platform(hostname: str) -> bool:
    """Block known Google review surfaces rather than attempting extraction."""

    host = hostname.lower().rstrip(".")
    return (
        host in {"g.page", "goo.gl", "maps.app.goo.gl"}
        or host.endswith(".g.page")
        or host.endswith(".goo.gl")
        or bool(re.search(r"(^|\.)google\.[a-z.]+$", host))
    )


def validate_public_url(url: str, resolver=_default_resolver) -> str:
    """Return a normalized public HTTP(S) URL or raise WebsiteImportError."""

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise WebsiteImportError("Enter a complete public HTTP or HTTPS URL.")
    if parsed.username or parsed.password:
        raise WebsiteAccessBlockedError("URLs containing credentials are blocked.")
    hostname = parsed.hostname.rstrip(".").lower()
    if _is_restricted_platform(hostname):
        raise WebsiteAccessBlockedError(
            "Direct import from Google review surfaces is blocked. Use an authorized export instead."
        )
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise WebsiteAccessBlockedError("Local and private network destinations are blocked.")
    try:
        addresses = resolver(hostname)
    except OSError as error:
        raise WebsiteImportError("The website hostname could not be resolved.") from error
    if not addresses:
        raise WebsiteImportError("The website hostname did not resolve to an address.")
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address)
        except ValueError as error:
            raise WebsiteAccessBlockedError("The website resolved to an invalid network address.") from error
        if not ip.is_global:
            raise WebsiteAccessBlockedError(
                "Local, private, reserved, and link-local destinations are blocked."
            )
    return parsed.geturl()


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = value.get("value") or value.get("name") or value.get("@id") or ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip()


def _normalize_date(value: Any) -> str:
    raw = _text(value)
    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ]|$)", raw)
    return match.group(1) if match else raw


def _normalize_rating(value: Any) -> str:
    raw = _text(value)
    if re.fullmatch(r"[1-5]", raw):
        return raw
    match = re.search(r"\b([1-5])(?:\.0)?\s*(?:/|out\s+of)\s*5\b", raw, re.IGNORECASE)
    return match.group(1) if match else raw


def _identifier(value: Any) -> str:
    if isinstance(value, dict):
        return _text(value.get("value") or value.get("@id") or value.get("name"))
    return _text(value)


def _generated_id(prefix: str, source_url: str, *parts: str) -> str:
    payload = "\x1f".join([source_url, *parts]).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:16]}"


def _complete_identifiers(
    rows: list[dict[str, str]], source_url: str, notices: list[str]
) -> None:
    for index, row in enumerate(rows, start=1):
        if not row.get("practice_id") and row.get("practice_name"):
            row["practice_id"] = _generated_id(
                "practice", urlparse(source_url).netloc, row["practice_name"]
            )
            notices.append(
                f"Record {index}: practice_id was generated from the source host and practice name."
            )
        if not row.get("review_id"):
            row["review_id"] = _generated_id(
                "review",
                source_url,
                row.get("practice_name", ""),
                row.get("review_date", ""),
                row.get("rating", ""),
                row.get("review_text", ""),
            )
            notices.append(
                f"Record {index}: review_id was generated from extracted content; content changes can change this identifier."
            )


def _schema_type_is_review(value: Any) -> bool:
    types = value if isinstance(value, list) else [value]
    return any(_text(item).rstrip("/").split("/")[-1].lower() == "review" for item in types)


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _walk_json_reviews(value: Any, reviewed_parent: dict[str, Any] | None = None):
    if isinstance(value, dict):
        if _schema_type_is_review(value.get("@type")):
            yield value, reviewed_parent or {}
            return
        for key, child in value.items():
            child_parent = value if key in {"review", "reviews"} else reviewed_parent
            yield from _walk_json_reviews(child, child_parent)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json_reviews(child, reviewed_parent)


def _extract_json_ld(soup: BeautifulSoup, source_url: str) -> _Extraction:
    rows: list[dict[str, str]] = []
    notices: list[str] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        entity_index = {
            _text(item.get("@id")): item
            for item in _walk_json(payload)
            if isinstance(item, dict) and item.get("@id")
        }
        for item, reviewed_parent in _walk_json_reviews(payload):
            reviewed_value = item.get("itemReviewed")
            if isinstance(reviewed_value, dict):
                reviewed = reviewed_value
            elif reviewed_value:
                reviewed = {"name": _text(reviewed_value)}
            else:
                reviewed = reviewed_parent
            reviewed_reference = _text(reviewed.get("@id"))
            if reviewed_reference in entity_index:
                reviewed = {**entity_index[reviewed_reference], **reviewed}
            rating = item.get("reviewRating") if isinstance(item.get("reviewRating"), dict) else {}
            review_url = _text(item.get("url"))
            rows.append(
                {
                    "review_id": _identifier(item.get("@id") or item.get("identifier")),
                    "practice_id": _identifier(reviewed.get("@id") or reviewed.get("identifier")),
                    "practice_name": _text(reviewed.get("name")),
                    "review_date": _normalize_date(item.get("datePublished")),
                    "rating": _normalize_rating(rating.get("ratingValue")),
                    "review_text": _text(item.get("reviewBody") or item.get("description")),
                    "source_label": urljoin(source_url, review_url) if review_url else source_url,
                }
            )
    _complete_identifiers(rows, source_url, notices)
    return _Extraction(rows, notices)


def _element_value(element: Tag | None, attribute: str = "") -> str:
    if element is None:
        return ""
    if attribute and element.has_attr(attribute):
        return _text(element.get(attribute))
    for candidate in ("content", "datetime", "data-rating", "value"):
        if element.has_attr(candidate):
            return _text(element.get(candidate))
    return element.get_text(" ", strip=True)


def _extract_microdata(soup: BeautifulSoup, source_url: str) -> _Extraction:
    rows: list[dict[str, str]] = []
    notices: list[str] = []
    for item in soup.select('[itemscope][itemtype*="schema.org/Review" i]'):
        reviewed = item.select_one('[itemprop="itemReviewed"]')
        nested_practice_name = (
            _element_value(reviewed.select_one('[itemprop="name"]')) if reviewed else ""
        )
        practice_name = nested_practice_name or _element_value(reviewed)
        rating = item.select_one('[itemprop="ratingValue"]')
        source = item.select_one('[itemprop="url"]')
        rows.append(
            {
                "review_id": _text(item.get("itemid") or item.get("data-review-id") or item.get("id")),
                "practice_id": _text(
                    (reviewed.get("itemid") or reviewed.get("data-practice-id") or reviewed.get("id"))
                    if reviewed
                    else ""
                ),
                "practice_name": practice_name,
                "review_date": _normalize_date(_element_value(item.select_one('[itemprop="datePublished"]'))),
                "rating": _normalize_rating(_element_value(rating)),
                "review_text": _element_value(
                    item.select_one('[itemprop="reviewBody"], [itemprop="description"]')
                ),
                "source_label": urljoin(source_url, _element_value(source, "href")) if source else source_url,
            }
        )
    _complete_identifiers(rows, source_url, notices)
    return _Extraction(rows, notices)


def _selected_value(container: Tag, selector: str, attribute: str = "") -> str:
    if not selector:
        return ""
    element = container if selector == ":scope" else container.select_one(selector)
    return _element_value(element, attribute)


def _extract_custom_selectors(
    soup: BeautifulSoup, source_url: str, config: SelectorConfig
) -> _Extraction:
    rows: list[dict[str, str]] = []
    notices: list[str] = []
    try:
        containers = soup.select(config.container)
        for item in containers:
            review_id = _selected_value(item, config.review_id, config.review_id_attribute)
            practice_id = _selected_value(item, config.practice_id, config.practice_id_attribute)
            source = _selected_value(item, config.source_url, config.source_url_attribute)
            rows.append(
                {
                    "review_id": review_id or _text(item.get("data-review-id") or item.get("id")),
                    "practice_id": practice_id or _text(item.get("data-practice-id")),
                    "practice_name": _selected_value(item, config.practice_name),
                    "review_date": _normalize_date(
                        _selected_value(item, config.review_date, config.date_attribute)
                    ),
                    "rating": _normalize_rating(
                        _selected_value(item, config.rating, config.rating_attribute)
                    ),
                    "review_text": _selected_value(item, config.review_text),
                    "source_label": urljoin(source_url, source) if source else source_url,
                }
            )
    except SelectorSyntaxError as error:
        raise UnsupportedReviewFormatError(f"A configured CSS selector is invalid: {error}") from error
    _complete_identifiers(rows, source_url, notices)
    return _Extraction(rows, notices)


def _extract_article_reviews(soup: BeautifulSoup, source_url: str) -> _Extraction:
    config = SelectorConfig(
        container="article.review",
        review_text=".review-text",
        rating=".review-rating",
        review_date="time[datetime]",
        practice_name=".review-practice",
        source_url="a.review-source[href]",
    )
    return _extract_custom_selectors(soup, source_url, config)


def _looks_like_reviews(soup: BeautifulSoup) -> bool:
    return bool(
        soup.select_one(
            '[class*="review" i], [id*="review" i], [itemprop*="review" i], [data-review-id]'
        )
    )


def parse_reviews_html(
    html_text: str,
    source_url: str,
    selector_config: SelectorConfig | None = None,
) -> WebsiteImportResult:
    """Attempt each supported extraction method and report the detected format."""

    soup = BeautifulSoup(html_text, "html.parser")
    methods: list[tuple[str, Callable[[], _Extraction]]] = [
        ("Schema.org Review JSON-LD", lambda: _extract_json_ld(soup, source_url)),
        ("Schema.org Review Microdata", lambda: _extract_microdata(soup, source_url)),
    ]
    if selector_config is not None:
        methods.append(
            ("Configured CSS selectors", lambda: _extract_custom_selectors(soup, source_url, selector_config))
        )
    methods.append(("article.review HTML", lambda: _extract_article_reviews(soup, source_url)))

    incomplete_result: WebsiteImportResult | None = None
    for format_name, extractor in methods:
        extraction = extractor()
        if not extraction.rows:
            continue
        loaded = load_review_rows(extraction.rows)
        result = WebsiteImportResult(
            reviews=loaded.reviews,
            issues=loaded.issues,
            detected_format=format_name,
            notices=extraction.notices,
        )
        if result.reviews:
            return result
        if incomplete_result is None:
            incomplete_result = result
    if incomplete_result is not None:
        return incomplete_result
    if _looks_like_reviews(soup):
        raise UnsupportedReviewFormatError(
            "The page appears to contain reviews, but its HTML does not match JSON-LD, Schema.org Review Microdata, article.review, or the configured CSS selectors."
        )
    raise NoReviewsFoundError(
        "The page was accessible, but no review records were found in the supported formats."
    )


def _robots_allows(url: str, session: requests.Session, resolver) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    validate_public_url(robots_url, resolver)
    try:
        response = session.get(
            robots_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
        )
    except requests.RequestException as error:
        raise WebsiteAccessBlockedError(
            "Website access was blocked because robots.txt could not be verified."
        ) from error
    if response.status_code == 404:
        return True
    if response.status_code >= 300:
        raise WebsiteAccessBlockedError(
            f"Website access was blocked because robots.txt returned HTTP {response.status_code}."
        )
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def fetch_reviews(
    url: str,
    *,
    selector_config: SelectorConfig | None = None,
    session: requests.Session | None = None,
    resolver=_default_resolver,
    check_robots: bool = True,
) -> WebsiteImportResult:
    """Fetch a public page safely, follow validated redirects, and parse reviews."""

    active_session = session or requests.Session()
    current_url = validate_public_url(url, resolver)
    checked_origins: set[str] = set()
    for redirect_count in range(MAX_REDIRECTS + 1):
        parsed = urlparse(current_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if check_robots and origin not in checked_origins:
            if not _robots_allows(current_url, active_session, resolver):
                raise WebsiteAccessBlockedError(
                    "Website access was blocked because robots.txt does not permit this import."
                )
            checked_origins.add(origin)
        try:
            response = active_session.get(
                current_url,
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            )
        except requests.Timeout as error:
            raise WebsiteImportError("The website request timed out.") from error
        except requests.RequestException as error:
            raise WebsiteImportError("The website request failed.") from error
        if response.is_redirect or response.is_permanent_redirect:
            if redirect_count == MAX_REDIRECTS:
                raise WebsiteAccessBlockedError("Website access was blocked after too many redirects.")
            location = response.headers.get("Location")
            if not location:
                raise WebsiteAccessBlockedError("Website access was blocked by an invalid redirect.")
            current_url = validate_public_url(urljoin(current_url, location), resolver)
            continue
        if response.status_code in {401, 403, 429}:
            raise WebsiteAccessBlockedError(
                f"Website access was blocked or rate-limited with HTTP {response.status_code}."
            )
        if response.status_code >= 400:
            raise WebsiteImportError(f"The website returned HTTP {response.status_code}.")
        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" not in content_type:
            raise UnsupportedReviewFormatError("The URL did not return an HTML page.")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise WebsiteAccessBlockedError("Website access was blocked because the HTML page exceeds 2 MB.")
        return parse_reviews_html(response.text, current_url, selector_config)
    raise WebsiteImportError("The website import could not be completed.")
