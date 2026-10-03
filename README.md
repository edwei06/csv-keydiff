# csv-keydiff

Compare CSV snapshots by record identity. Row order and column order do not
create noise. Composite keys, explicit duplicate rejection, and deterministic
JSON/Markdown reports make small data exports easier to review.

Python 3.10+, zero runtime dependencies, completely offline.

## Quick start

~~~sh
python -m pip install .
csv-keydiff examples/before.csv examples/after.csv --key team --key id
~~~

~~~text
1 added, 1 removed, 1 changed, 1 unchanged
~~~

Run without installing using `python -m csv_keydiff` from the repository.
Repeat `--key COLUMN` for composite keys. Key values remain strings, including
leading zeros. A key must be present, nonempty, and unique in each file.

## Reports and automation

~~~sh
csv-keydiff before.csv after.csv --key id --format json --fail-on-change
csv-keydiff before.csv after.csv --key id --format markdown
~~~

JSON includes `summary`, `columns_added`, `columns_removed`, `added`,
`removed`, and `changed`. Added/removed records contain their full unignored
rows; changed records include before/after values for changed fields only.
Output can therefore contain the input data you choose to compare.

Exit codes: `0` successful comparison, `1` differences when
`--fail-on-change` is enabled, `2` input or argument errors.
Schema changes also count as differences.

## Controls

- `--ignore COLUMN`: omit a column from both schema and value comparison.
  Repeat as needed. Key columns cannot be ignored; unknown names are rejected.
- `--trim`: strip surrounding whitespace from cell values before comparison.
- `--delimiter tab` or a single character: compare TSV or semicolon exports.
- `--format text|json|markdown`: summary, machine report, or escaped table.

Header names always have surrounding whitespace removed. Duplicate or empty
header names are rejected. Blank records are skipped. Quoted commas, multiline
cells, UTF-8 BOM, and CRLF are supported through Python's strict CSV reader.
Malformed records and duplicate keys produce errors instead of silent data loss.

## Comparison semantics

Only columns present in both files are compared for cell changes. Added/removed
columns are reported separately. A matched row with identical shared fields is
counted as unchanged even if the schema differs. Records and field names are
sorted lexicographically to make repeated reports stable.

This is an in-memory snapshot tool. It performs exact string comparison, not
numeric coercion, fuzzy matching, database migration, or spreadsheet formula
evaluation. For datasets that do not fit comfortably in memory, use a streaming
or database-oriented tool. Python's standard CSV field-size limit applies.

## Development

~~~sh
python -m unittest discover -s tests -v
~~~

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## Related tools

[simonw/csv-diff](https://github.com/simonw/csv-diff) supports CSV and JSON
comparisons, while [csvdiff](https://github.com/aswinkarthik/csvdiff) is a Go tool.
csv-keydiff focuses on composite identity, strict input validation, and a
standard-library-only Python installation. This is an independent implementation.

Licensed under [MIT](LICENSE).
