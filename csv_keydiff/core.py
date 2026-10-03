"""Compare validated CSV tables using stable, string-valued record keys."""
import csv
from dataclasses import dataclass
from pathlib import Path


class InputError(ValueError):
    """An input cannot be compared without losing or misidentifying records."""


@dataclass
class Table:
    columns: tuple[str, ...]
    rows: dict[tuple[str, ...], dict[str, str]]


def load_table(path: Path, keys: tuple[str, ...], delimiter: str = ",",
               trim: bool = False) -> Table:
    if not keys or len(set(keys)) != len(keys):
        raise InputError("Specify one or more distinct key columns")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, delimiter=delimiter, strict=True)
        try:
            header = next(reader)
        except StopIteration:
            raise InputError("CSV input is empty") from None
        columns = tuple(column.strip() for column in header)
        if not columns or any(not column for column in columns):
            raise InputError("CSV header contains an empty column name")
        if len(set(columns)) != len(columns):
            raise InputError("CSV header contains duplicate column names")
        missing = set(keys) - set(columns)
        if missing:
            raise InputError("Missing key columns: " + ", ".join(sorted(missing)))
        rows: dict[tuple[str, ...], dict[str, str]] = {}
        for values in reader:
            if not values:
                continue
            if len(values) != len(columns):
                raise InputError(f"Record ending at line {reader.line_num} has the wrong field count")
            if trim:
                values = [value.strip() for value in values]
            row = dict(zip(columns, values))
            identity = tuple(row[column] for column in keys)
            if any(value == "" for value in identity):
                raise InputError(f"Empty key in record ending at line {reader.line_num}")
            if identity in rows:
                raise InputError(f"Duplicate key in record ending at line {reader.line_num}")
            rows[identity] = row
    return Table(columns, rows)


def compare(left: Table, right: Table, keys: tuple[str, ...],
            ignore: set[str] | None = None) -> dict:
    """Ignore record order and compare shared columns; report schema changes separately."""
    ignore = ignore or set()
    if ignore & set(keys):
        raise InputError("Key columns cannot be ignored")
    unknown = ignore - (set(left.columns) | set(right.columns))
    if unknown:
        raise InputError("Unknown ignored columns: " + ", ".join(sorted(unknown)))
    left_columns = set(left.columns) - ignore
    right_columns = set(right.columns) - ignore
    comparable = sorted((left_columns & right_columns) - set(keys))

    def identity(key):
        return dict(zip(keys, key))

    def record(table, key):
        return {"key": identity(key),
                "row": {column: value for column, value in sorted(table.rows[key].items())
                        if column not in ignore}}

    left_keys, right_keys = set(left.rows), set(right.rows)
    added = [record(right, key) for key in sorted(right_keys - left_keys)]
    removed = [record(left, key) for key in sorted(left_keys - right_keys)]
    changed = []
    for key in sorted(left_keys & right_keys):
        fields = {column: {"before": left.rows[key][column], "after": right.rows[key][column]}
                  for column in comparable
                  if left.rows[key][column] != right.rows[key][column]}
        if fields:
            changed.append({"key": identity(key), "fields": fields})
    columns_added = sorted(right_columns - left_columns)
    columns_removed = sorted(left_columns - right_columns)
    equal = not any((added, removed, changed, columns_added, columns_removed))
    return {"equal": equal,
            "summary": {"left_rows": len(left.rows), "right_rows": len(right.rows),
                        "added": len(added), "removed": len(removed),
                        "changed": len(changed),
                        "unchanged": len(left_keys & right_keys) - len(changed)},
            "columns_added": columns_added, "columns_removed": columns_removed,
            "added": added, "removed": removed, "changed": changed}


def markdown(report: dict) -> str:
    """Render changes safely inside a Markdown table."""
    def cell(value):
        return (str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace("\\", "&#92;").replace("|", "&#124;").replace(chr(96), "&#96;")
                .replace("\r", " ").replace("\n", "<br>"))

    def label(key):
        return ", ".join(f"{name}={value}" for name, value in key.items())

    summary = report["summary"]
    lines = ["# CSV comparison", "",
             f"{summary['added']} added, {summary['removed']} removed, "
             f"{summary['changed']} changed; equal: {str(report['equal']).lower()}", ""]
    for name in ("columns_added", "columns_removed"):
        if report[name]:
            lines.extend([f"{name.replace('_', ' ').capitalize()}: " +
                          ", ".join(cell(value) for value in report[name]), ""])
    lines.extend(["| Change | Key | Column | Before | After |",
                  "| --- | --- | --- | --- | --- |"])
    for kind in ("removed", "added"):
        for record in report[kind]:
            for column, value in record["row"].items():
                before, after = (value, "") if kind == "removed" else ("", value)
                lines.append("| " + " | ".join(map(cell, (kind, label(record["key"]),
                                                          column, before, after))) + " |")
    for record in report["changed"]:
        for column, values in record["fields"].items():
            lines.append("| " + " | ".join(map(cell, ("changed", label(record["key"]),
                                                      column, values["before"], values["after"]))) + " |")
    return "\n".join(lines) + "\n"
