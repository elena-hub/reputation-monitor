"""Command-line interface for the review snapshot monitor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import analyze_reviews
from .loader import LoadResult, load_reviews
from .reporter import write_alerts_csv, write_html_report


def build_parser() -> argparse.ArgumentParser:
    """Create and return the command-line argument parser."""

    parser = argparse.ArgumentParser(
        description="Compare two fictional review CSV snapshots and report new low ratings."
    )
    parser.add_argument(
        "--previous", type=Path, default=Path("data/reviews_previous.csv"), help="Previous CSV snapshot"
    )
    parser.add_argument(
        "--current", type=Path, default=Path("data/reviews_current.csv"), help="Current CSV snapshot"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("reports"), help="Directory for generated reports"
    )
    parser.add_argument(
        "--maximum-rating", type=int, choices=range(1, 6), default=2, metavar="1-5",
        help="Highest rating that creates an alert (default: 2)",
    )
    return parser


def _print_issues(label: str, result: LoadResult) -> None:
    for issue in result.issues:
        print(f"WARNING: {label} row {issue.row_number}: {issue.message}", file=sys.stderr)


def run(args: argparse.Namespace) -> int:
    """Run monitoring with parsed arguments and return a process exit code."""

    try:
        previous = load_reviews(args.previous)
        current = load_reviews(args.current)
    except (FileNotFoundError, PermissionError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    _print_issues("previous snapshot", previous)
    _print_issues("current snapshot", current)
    analysis = analyze_reviews(previous.reviews, current.reviews, args.maximum_rating)

    alerts_path = args.output_dir / "alerts.csv"
    report_path = args.output_dir / "monitoring_report.html"
    try:
        write_alerts_csv(
            analysis.new_low_rating_reviews,
            alerts_path,
            maximum_rating=args.maximum_rating,
        )
        write_html_report(
            analysis=analysis,
            previous_count=len(previous.reviews),
            current_count=len(current.reviews),
            previous_issues=previous.issues,
            current_issues=current.issues,
            output_path=report_path,
            maximum_rating=args.maximum_rating,
        )
    except (OSError, ValueError) as error:
        print(f"ERROR: Could not write reports: {error}", file=sys.stderr)
        return 1

    print("Reputation monitoring complete")
    print(f"Valid previous reviews: {len(previous.reviews)}")
    print(f"Valid current reviews:  {len(current.reviews)}")
    print(f"Malformed rows skipped: {len(previous.issues) + len(current.issues)}")
    print(f"New reviews:            {len(analysis.new_reviews)}")
    print(f"New low-rating alerts:  {len(analysis.new_low_rating_reviews)}")
    print(f"Alerts CSV: {alerts_path}")
    print(f"HTML report: {report_path}")
    return 0


def main() -> int:
    """Parse command-line arguments and run the application."""

    return run(build_parser().parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
