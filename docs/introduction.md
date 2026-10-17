# Introduction

## Purpose

Reputation Monitor validates authorized review records, summarizes current ratings, and—when a previous snapshot is available—detects newly observed reviews. The dashboard slider selects the maximum rating that triggers an alert. Its default value of 2 flags newly detected 1-star and 2-star reviews.

## Interfaces

- The Streamlit dashboard accepts a current CSV, an optional previous CSV, or supported review data from an authorized public webpage.

Website extraction automatically checks Schema.org Review JSON-LD, Schema.org Review Microdata, optional operator-provided CSS selectors, and the documented `article.review` layout. Extracted records are previewed before analysis.
- The CLI compares two CSV snapshots and writes reports to disk.

Without a previous snapshot, the dashboard displays current metrics only. It does not label reviews as new or generate new-review alerts. The software performs numerical triage; it does not determine whether a review is accurate, unlawful, urgent, or suitable for removal.

All bundled data is synthetic. Keep patient or health information out of input files and reports.

Continue with [Installation](installation.md), then [Quickstart](quickstart.md).
