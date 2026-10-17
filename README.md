# Reputation Monitor

Reputation Monitor is a local Python 3.11+ application for reviewing authorized reputation data. It validates CSV records, summarizes current ratings, compares review snapshots by stable identifier, and creates alerts for newly detected reviews at or below a configurable rating threshold.

The project provides both a Streamlit dashboard and a command-line interface. It does not connect to Google or provide continuous monitoring of any review platform.

## Live demo

Streamlit Community Cloud deployment is prepared but has not been authorized or published. After deployment, the verified public demo URL will be added here.

Deployment settings:

| Setting | Value |
|---|---|
| Repository | `elena-hub/reputation-monitor` |
| Branch | `main` |
| Main file path | `streamlit_app.py` |
| Python | `3.12` |
| Secrets | None required |

Community Cloud detects the root `uv.lock` and installs the local `reputation-monitor` package with its declared dependencies. The application does not require system packages or Mac-specific paths.

## Key features

- Import a current CSV and an optional previous CSV in Streamlit.
- Import authorized public webpages containing Schema.org Review JSON-LD, Schema.org Review Microdata, a configured CSS-selector layout, or the supported `article.review` structure.
- Preview website-extracted records before analysis.
- Validate required values, ISO-format dates, ratings from 1 to 5, and duplicate review IDs.
- Report imported and rejected review counts without exposing record-level diagnostics in the main interface.
- Calculate review count, average rating, and rating distribution.
- Detect new reviews by comparing stable `review_id` values.
- Alert on newly detected reviews at or below a selected rating; the default is 2 stars.
- Export alerts as CSV and a standalone, HTML-escaped monitoring report.
- Preserve website access controls, including `robots.txt`, public-network destination checks, redirect validation, response-size limits, and request timeouts.
- Test CSV, analysis, reporting, dashboard, CLI, and website-import behavior with pytest.

## Requirements

- Python 3.11 or newer
- `pip`
- A modern browser for Streamlit

## Installation

Clone the repository and create an isolated environment:

```bash
git clone https://github.com/elena-hub/reputation-monitor.git
cd reputation-monitor
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install ".[dev]"
```

On Windows PowerShell, activate the environment with:

```powershell
.venv\Scripts\Activate.ps1
```

## Run locally

Start the Streamlit dashboard:

```bash
streamlit run streamlit_app.py
```

Open the local URL printed by Streamlit. To reproduce the supplied comparison, upload:

- `data/reviews_current.csv` as the current snapshot;
- `data/reviews_previous.csv` as the previous snapshot.

Run the equivalent command-line analysis:

```bash
reputation-monitor
```

The CLI writes `reports/alerts.csv` and `reports/monitoring_report.html`. Override the paths or alert threshold as needed:

```bash
reputation-monitor \
  --previous data/reviews_previous.csv \
  --current data/reviews_current.csv \
  --output-dir reports \
  --maximum-rating 3
```

Use `reputation-monitor --help` for the complete option reference.

## CSV import format

CSV files must be UTF-8 and contain these seven headers:

```csv
review_id,practice_id,practice_name,review_date,rating,review_text,source_label
```

Example using fictional data:

```csv
sample-001,practice-demo,Clinique Exemple Rivoli,2026-10-14,5,The reception team was helpful.,Authorized CSV export
sample-002,practice-demo,Clinique Exemple Rivoli,2026-10-15,2,The appointment began later than expected.,Authorized CSV export
```

Important rules:

- Keep `review_id` stable for the same review across snapshots.
- Use dates in `YYYY-MM-DD` form.
- Use whole-number ratings from 1 through 5.
- Provide every required value.
- Do not include patient health information or other unnecessary sensitive data.
- Do not overwrite the bundled synthetic fixtures with operational data; use separately named, ignored input files.

See [`data/reviews_sample.csv`](data/reviews_sample.csv) for a downloadable template.

## Architecture

| Component | Responsibility |
|---|---|
| `streamlit_app.py` | Starts the Streamlit interface. |
| `dashboard.py` | Coordinates uploads, website import, previews, settings, metrics, and downloads. |
| `loader.py` | Reads CSV or normalized records and validates required fields. |
| `web_importer.py` | Retrieves authorized public HTML, enforces network safeguards, detects supported formats, and normalizes records. |
| `workflow.py` | Calculates current metrics and coordinates optional snapshot comparison. |
| `analyzer.py` | Detects new review IDs and applies the maximum-rating alert rule. |
| `reporter.py` | Produces CSV alerts and escaped HTML reports. |
| `cli.py` | Provides repeatable command-line execution and exit behavior. |

The core flow is:

```text
CSV or supported webpage
        ↓
validation and normalization
        ↓
current metrics + optional snapshot comparison
        ↓
rating-threshold alerts
        ↓
Streamlit display, CSV alerts, and HTML report
```

## Project structure

```text
reputation-monitor/
├── data/                    # Synthetic snapshots and CSV template
├── docs/                    # Application operating guides
├── src/reputation_monitor/  # Application package
├── tests/                   # Automated tests and local HTML fixtures
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── README.md
├── streamlit_app.py
└── uv.lock
```

Generated reports, local imports, virtual environments, caches, credentials, and the separately maintained website documentation are excluded from the public repository.

## Testing

Install the development dependency and run the complete suite:

```bash
python -m pip install ".[dev]"
python -m pytest
```

The tests use local synthetic CSV files and HTML fixtures. They do not make live website requests.

## Website import safeguards

Import only pages you own or are authorized to process. The importer:

- permits only public HTTP(S) destinations;
- rejects credentials embedded in URLs;
- blocks localhost, private, reserved, and link-local destinations;
- blocks Google review surfaces;
- checks `robots.txt` and validates each redirect;
- applies response-size and connection/read-time limits;
- does not bypass authentication, CAPTCHAs, anti-bot controls, or rate limits.

If access is restricted or the page format is unsupported, use an authorized CSV export instead.

## Known limitations

- Monitoring is run manually; there is no scheduler or notification service.
- The application has no database and does not retain historical runs automatically.
- It does not detect deleted reviews or edits to a known `review_id`.
- Website import supports static HTML only and does not render JavaScript.
- Custom CSS selectors depend on stable source markup.
- It does not classify sentiment, verify review accuracy, or determine legal status.
- A low rating is a numerical alert signal, not proof that a review is false, harmful, or removable.
- Reusing an output directory overwrites the existing report filenames.
- The public dashboard has no user authentication or per-user request throttling. Monitor resource use when website import is enabled for anonymous visitors.
- Website destinations are checked before every request and redirect, but application-level DNS checks cannot completely eliminate a DNS-change race between validation and connection.

## Documentation

- [Official technical documentation](https://reputation-management-service.com/en/docs/python-reputation-monitoring/)
- [Installation guide](docs/installation.md)
- [Quickstart](docs/quickstart.md)
- [Configuration](docs/configuration.md)
- [Troubleshooting](docs/troubleshooting.md)

## Data protection

The bundled reviews and medical-practice names are synthetic. The application processes data locally and includes no telemetry or database. Operators remain responsible for authorization, data minimization, access control, retention, and deletion.

## License

The repository currently contains the MIT License. Confirm that this license is appropriate for your intended release before publishing. See [`LICENSE`](LICENSE).
