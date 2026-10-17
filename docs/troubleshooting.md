# Troubleshooting

| Problem | Verification | Action |
|---|---|---|
| `streamlit` or `reputation-monitor` is not found | Run `python --version` and inspect the prompt for the active environment. | Activate `.venv` and run `python -m pip install ".[dev]"`. |
| CSV cannot be imported | Compare the header with `data/reviews_sample.csv`; confirm UTF-8 encoding. | Restore all seven exact column names and correct invalid records. |
| Some reviews are rejected | Read the imported and rejected counts in the dashboard confirmation. | Correct missing, invalid, or duplicated information in the source CSV, then upload it again. Detailed record findings remain in application logs. |
| New-review count is not calculated | Check whether a previous CSV was uploaded. | Supply a valid previous snapshot when comparison is required. |
| Alert count is unexpected | Confirm stable IDs and the selected maximum alert rating. | Correct IDs at the source; do not create new IDs for unchanged reviews. |
| Website URL is blocked | Check whether it resolves to localhost, private, reserved, or link-local space. | Use an authorized public HTTP(S) destination; do not bypass the control. |
| Website import reports no reviews | Inspect the returned HTML, not only the rendered browser view. | Confirm the page contains review records in HTML rather than JavaScript-loaded content. |
| Website import reports unsupported HTML | Check for Schema.org Review JSON-LD, Review Microdata, `article.review`, or stable CSS selectors. | Configure selectors for an authorized static layout or use an authorized CSV export. |
| Extracted records are skipped | Review the preview findings for missing rating, date, practice name, or text. | Correct the source markup or use a complete authorized export; the importer does not invent missing values. |
| Robots check fails or disallows access | Open the site’s `/robots.txt`. | Respect the rule and use a permitted export; do not retry to evade it. |
| HTML text looks encoded | Look for `&lt;` or `&amp;` in page source. | This is expected output escaping; a browser displays the characters as text. |

For reproducible diagnostics, record the command, Python version, input filenames, threshold, and exact error without copying sensitive review content into support messages.

## CSV import confirmations

After a complete current-file import, the dashboard displays **Current reviews imported successfully — X reviews ready for analysis.** After a complete previous-file import, it displays **Previous reviews imported successfully — X reviews available for comparison.** The application replaces `X` with the actual imported count.

When one or more records are rejected, the message reports both the number ready to use and the number rejected. The dashboard summarizes the reason as missing, invalid, or duplicated required information; record-level details are written to application logs. If no reviews can be imported, correct the file before continuing.

## Website access is restricted

When published access rules, authentication, anti-bot controls, or rate limits prevent an authorized import, the dashboard shows only this recovery message:

> **Reviews couldn't be imported from this website.**
>
> This website restricts automated access. You can still analyze your reviews by uploading a CSV file.

Select **Switch to CSV Upload**. The selected alert threshold remains unchanged. Upload an authorized current CSV, then optionally upload a previous CSV to enable new-review detection. Do not attempt to bypass the website restriction.

If the dashboard instead reports an unsupported review format, the page was accessible but its markup did not match a supported extractor. Configure stable CSS selectors for an authorized layout or use CSV upload.
