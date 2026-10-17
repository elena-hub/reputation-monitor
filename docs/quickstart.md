# Quickstart

## Purpose

Run the dashboard with bundled synthetic snapshots and download both report formats.

## Prerequisites

Complete [Installation](installation.md).

## Procedure

1. Start the application:

   ```bash
   streamlit run streamlit_app.py
   ```

2. Open the local URL printed in the terminal.
3. Keep **Alert me about new reviews rated 2 stars or less** at its default value of `2`. At this setting, newly detected 1-star and 2-star reviews trigger alerts.
4. Select **CSV upload**.
5. Upload `data/reviews_current.csv` as the current CSV.
6. Upload `data/reviews_previous.csv` as the previous CSV.
7. Review the summary, rating chart, alerts, details, and import confirmation messages.
8. Select **Download HTML report** and **Download CSV alerts**.

Expected result: the dashboard reports **Current reviews imported with issues — 18 reviews ready for analysis; 2 reviews rejected because required information was missing, invalid, or duplicated.** It also shows three new reviews and two new alerts. The previous-file confirmation reports 15 reviews available for comparison. The CLI produces the same comparison with:

```bash
reputation-monitor
```

If only the current CSV is uploaded, current metrics remain available, while new-review and alert counts show **Not calculated**.
