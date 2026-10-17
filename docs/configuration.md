# Configuration

## New-review alert rating

The dashboard slider reads **Alert me about new reviews rated 2 stars or less** at its default setting. The number updates with the selected value from 1 through 5. The selected rating is the maximum rating that triggers an alert; choosing `3`, for example, flags newly detected 1-, 2-, and 3-star reviews.

The explanation beneath the slider reads: **Choose which ratings should trigger an alert when new reviews are detected.** Existing reviews are not flagged again when comparing snapshots because alerts apply only to review IDs absent from the previous snapshot.

In the CLI, set the same maximum alert rating with:

```bash
reputation-monitor --maximum-rating 3
```

Changing the slider updates the alert threshold without changing the rating calculations. The selected value also controls CSV `alert_reason` text and the HTML alert heading.

## CLI paths

```bash
reputation-monitor \
  --previous data/reviews_previous.csv \
  --current data/reviews_current.csv \
  --output-dir reports \
  --maximum-rating 2
```

Both CSV files require the seven headers documented in the [official data reference](https://reputation-management-service.com/en/docs/python-reputation-monitoring/data-reference/).

After upload, the dashboard confirms the usable count as **Current reviews imported successfully — X reviews ready for analysis.** or **Previous reviews imported successfully — X reviews available for comparison.** If some records are rejected, it reports both the imported and rejected counts without exposing record-level validation details in the main interface. Those details remain available in application logs.

## Website import

The dashboard automatically attempts Schema.org Review JSON-LD, Schema.org Review Microdata, optional configured CSS selectors, and the documented `article.review` layout. For a custom layout, expand **Custom CSS selectors**, enable the option, and provide selectors for the review container, text, rating, date, and practice name. ID and source-link selectors are optional; attribute names can be configured where values are stored in HTML attributes.

After import, verify the detected format, preview, generated-ID notices, and validation findings. Select **Analyze previewed reviews** only after the preview is correct. Missing dates and ratings are never defaulted; incomplete records remain excluded with explicit validation messages.

Import only content you are permitted to access. The importer checks `robots.txt`, blocks private destinations and Google review surfaces, validates redirects, and does not bypass authentication, CAPTCHAs, anti-bot controls, rate limits, or JavaScript rendering.

Some public pages prohibit automated access through their published access rules or server controls. When those restrictions block an import, the dashboard displays:

> **Reviews couldn't be imported from this website.**
>
> This website restricts automated access. You can still analyze your reviews by uploading a CSV file.

Select **Switch to CSV Upload** directly below the message. The dashboard changes the import method immediately and preserves the selected maximum alert rating and other session settings. Upload a current CSV and, when comparison is required, an optional previous CSV using the schema in `data/reviews_sample.csv`.

An access restriction is different from an unsupported review format. A restriction prevents the application from retrieving permitted HTML. An unsupported format means the page was accessible, but its review markup did not match a supported structured-data, selector, or `article.review` layout.
