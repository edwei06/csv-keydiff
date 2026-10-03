"""CLI for record-oriented CSV comparisons."""
import argparse
import csv
import json
from pathlib import Path
import sys
from . import __version__
from .core import InputError, compare, load_table, markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare CSV files by one or more key columns.")
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--key", action="append", required=True, metavar="COLUMN",
                        help="Unique record key; repeat to use a composite key")
    parser.add_argument("--ignore", action="append", default=[], metavar="COLUMN")
    parser.add_argument("--trim", action="store_true", help="Strip whitespace from all cell values")
    parser.add_argument("--delimiter", default=",", help="One character, 'tab', or '\\t'")
    parser.add_argument("--format", choices=("text", "json", "markdown"), default="text")
    parser.add_argument("--fail-on-change", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    delimiter = "\t" if args.delimiter in ("tab", "\\t") else args.delimiter
    if len(delimiter) != 1 or delimiter in '\0\r\n"':
        parser.error("--delimiter must be one valid CSV delimiter")
    keys = tuple(args.key)
    try:
        left = load_table(Path(args.before), keys, delimiter, args.trim)
        right = load_table(Path(args.after), keys, delimiter, args.trim)
        report = compare(left, right, keys, set(args.ignore))
    except InputError as error:
        print(f"csv-keydiff: {error}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError, csv.Error):
        print("csv-keydiff: unable to read well-formed UTF-8 CSV input", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=True))
    elif args.format == "markdown":
        print(markdown(report), end="")
    else:
        summary = report["summary"]
        print(f"{summary['added']} added, {summary['removed']} removed, "
              f"{summary['changed']} changed, {summary['unchanged']} unchanged")
        for field in ("columns_added", "columns_removed"):
            if report[field]:
                print(field + ": " + ", ".join(report[field]))
    return 1 if args.fail_on_change and not report["equal"] else 0
