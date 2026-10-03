import contextlib
import csv
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from csv_keydiff.cli import main
from csv_keydiff.core import InputError, compare, load_table, markdown


class CsvTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.left = Path(self.temp.name) / "before.csv"
        self.right = Path(self.temp.name) / "after.csv"

    def write(self, left, right=None):
        self.left.write_bytes(left.encode("utf-8"))
        self.right.write_bytes((left if right is None else right).encode("utf-8"))

    def diff(self, keys=("id",), ignore=None, trim=False, delimiter=","):
        return compare(load_table(self.left, keys, delimiter, trim),
                       load_table(self.right, keys, delimiter, trim), keys, ignore)

    def test_row_and_column_order_do_not_matter(self):
        self.write("id,name\n1,A\n2,B\n", "name,id\nB,2\nA,1\n")
        self.assertTrue(self.diff()["equal"])

    def test_added_removed_changed_and_summary(self):
        self.write("id,name\n1,A\n2,B\n3,C\n", "id,name\n1,Z\n3,C\n4,D\n")
        report = self.diff()
        self.assertEqual({"left_rows": 3, "right_rows": 3, "added": 1,
                          "removed": 1, "changed": 1, "unchanged": 1}, report["summary"])
        self.assertEqual({"before": "A", "after": "Z"}, report["changed"][0]["fields"]["name"])

    def test_composite_key_prevents_identity_collisions(self):
        self.write("team,id,v\na,1,A\nb,1,B\n", "team,id,v\nb,1,Z\na,1,A\n")
        report = self.diff(("team", "id"))
        self.assertEqual({"team": "b", "id": "1"}, report["changed"][0]["key"])
        with self.assertRaises(InputError):
            self.diff(("id",))

    def test_schema_drift_is_separate_from_cell_changes(self):
        self.write("id,old,common\n1,a,x\n", "id,new,common\n1,b,x\n")
        report = self.diff()
        self.assertFalse(report["equal"])
        self.assertEqual(["new"], report["columns_added"])
        self.assertEqual(["old"], report["columns_removed"])
        self.assertEqual([], report["changed"])
        self.assertTrue(self.diff(ignore={"old", "new"})["equal"])

    def test_ignore_and_trim(self):
        self.write("id,name,time\n1, A ,old\n", "id,name,time\n1,A,new\n")
        self.assertTrue(self.diff(ignore={"time"}, trim=True)["equal"])
        self.assertFalse(self.diff(ignore={"time"})["equal"])

    def test_unknown_ignore_and_key_ignore_fail(self):
        self.write("id,name\n1,A")
        for ignored in ({"typo"}, {"id"}):
            with self.assertRaises(InputError):
                self.diff(ignore=ignored)

    def test_bom_crlf_quoted_comma_and_multiline(self):
        self.write('\ufeffid,name\r\n1,"A,B"\r\n2,"line\nnext"\r\n')
        self.assertTrue(self.diff()["equal"])
        self.assertEqual("line\nnext", load_table(self.left, ("id",)).rows[("2",)]["name"])

    def test_blank_lines_and_header_only(self):
        self.write("id,name\n\n")
        self.assertTrue(self.diff()["equal"])
        self.assertEqual(0, self.diff()["summary"]["left_rows"])

    def test_duplicate_empty_and_missing_keys_fail(self):
        for text in ("id,v\n1,x\n1,y", "id,v\n,x", "name,v\nx,y"):
            self.write(text)
            with self.assertRaises(InputError):
                self.diff()

    def test_bad_headers_and_field_counts_fail(self):
        for text in ("", "id,id\n1,2", "id,\n1,x", "id,v\n1", "id,v\n1,x,y"):
            self.write(text)
            with self.assertRaises(InputError):
                self.diff()

    def test_duplicate_cli_keys_fail(self):
        self.write("id,v\n1,x")
        with self.assertRaises(InputError):
            self.diff(("id", "id"))

    def test_strict_quotes(self):
        self.write('id,v\n1,"unterminated')
        with self.assertRaises(csv.Error):
            self.diff()

    def test_tab_delimiter(self):
        self.write("id\tname\n1\tA", "id\tname\n1\tB")
        self.assertEqual(1, self.diff(delimiter="\t")["summary"]["changed"])

    def test_values_remain_strings(self):
        self.write("id,v\n001,1.00", "id,v\n001,1")
        report = self.diff()
        self.assertEqual("001", report["changed"][0]["key"]["id"])
        self.assertEqual("1.00", report["changed"][0]["fields"]["v"]["before"])

    def test_sorted_results_are_stable(self):
        self.write("id,v\nz,Z\na,A", "id,v\nc,C\nb,B")
        self.assertEqual(["b", "c"], [item["key"]["id"] for item in self.diff()["added"]])

    def test_markdown_escapes_html_pipes_and_newlines(self):
        self.write("id,v\n1,old", 'id,v\n1,"<script>|' + chr(96) + '\\\nnext"')
        result = markdown(self.diff())
        self.assertNotIn("<script>", result)
        self.assertIn("&lt;script&gt;&#124;&#96;&#92;<br>next", result)

    def invoke(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = main([str(self.left), str(self.right), "--key", "id", *args])
        return code, output.getvalue(), errors.getvalue()

    def test_json_and_fail_on_change(self):
        self.write("id,v\n1,A", "id,v\n1,B")
        code, output, _ = self.invoke("--format", "json", "--fail-on-change")
        self.assertEqual(1, code)
        self.assertFalse(json.loads(output)["equal"])
        self.assertEqual(0, self.invoke()[0])

    def test_input_error_exit_code(self):
        self.write("id,v\n1,A\n1,B")
        self.assertEqual(2, self.invoke()[0])

    def test_module_subprocess(self):
        self.write("id,v\n1,A")
        result = subprocess.run([sys.executable, "-m", "csv_keydiff", str(self.left),
                                 str(self.right), "--key", "id", "--fail-on-change"],
                                capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
