# Changelog

All notable changes to Reputation Monitor are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and release versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-18

### Added

- Streamlit dashboard for CSV upload, current-review metrics, optional snapshot comparison, alert configuration, and report downloads.
- Command-line interface for repeatable two-snapshot analysis.
- UTF-8 CSV loading with required-field, date, rating, and duplicate-ID validation.
- New-review detection using stable review identifiers.
- Configurable alerts for newly detected reviews rated at or below a maximum value from 1 through 5, with a default threshold of 2.
- CSV alert output and standalone HTML monitoring reports with escaped dynamic content.
- Authorized website import for Schema.org Review JSON-LD, Schema.org Review Microdata, configured CSS selectors, and the supported `article.review` structure.
- Extracted-record preview and detected-format reporting before website data is analyzed.
- Website-import safeguards for public destinations, redirects, `robots.txt`, restricted platforms, response size, and request timeouts.
- User-facing recovery from restricted website imports through CSV upload without resetting the selected alert threshold.
- Imported and rejected review counts in dashboard CSV confirmations, with detailed diagnostics retained in application logs.
- Synthetic CSV datasets and local HTML fixtures.
- Automated tests covering loading, analysis, workflows, reporting, CLI behavior, dashboard behavior, and website imports.

### Security and privacy

- No telemetry, database, credential requirement, or bundled real patient/customer data.
- Private, reserved, loopback, and link-local network destinations are blocked during website import.
- Authentication, CAPTCHAs, anti-bot protections, rate limits, and website access restrictions are not bypassed.

[1.0.0]: https://github.com/elena-hub/reputation-monitor/releases/tag/v1.0.0
