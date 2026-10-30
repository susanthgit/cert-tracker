import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fetch_exams


class ExamUrlTests(unittest.TestCase):
    def test_configured_url_survives_each_record_constructor(self):
        for status, markdown in (("beta", None), ("active", "synthetic fixture"),
                                 ("retired", None)):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as output:
                # Synthetic records are confined to this temporary fixture directory.
                exam = dict(code="TEST-001", title="Synthetic fixture", level="beginner",
                            roles=[], products=[], category="Fixture", status=status,
                            exam_url="https://example.invalid/fixture")
                with patch.object(fetch_exams, "SITE_DIR", output), \
                     patch.object(fetch_exams, "load_exam_config", return_value=[exam]), \
                     patch.object(fetch_exams, "fetch_study_guide_markdown",
                                  return_value=markdown), contextlib.redirect_stdout(io.StringIO()):
                    fetch_exams.main()
                record = json.loads((Path(output) / "current_state.json").read_text(
                    encoding="utf-8"))["exams"][0]
                self.assertEqual(record["exam_url"], exam["exam_url"])

    def test_unconfigured_url_keeps_existing_default(self):
        with tempfile.TemporaryDirectory() as output:
            exam = dict(code="TEST-001", title="Synthetic fixture", level="beginner",
                        roles=[], products=[], category="Fixture", status="beta")
            with patch.object(fetch_exams, "SITE_DIR", output), \
                 patch.object(fetch_exams, "load_exam_config", return_value=[exam]), \
                 patch.object(fetch_exams, "fetch_study_guide_markdown", return_value=None), \
                 contextlib.redirect_stdout(io.StringIO()):
                fetch_exams.main()
            record = json.loads((Path(output) / "current_state.json").read_text(
                encoding="utf-8"))["exams"][0]
            self.assertEqual(record["exam_url"],
                             fetch_exams.EXAM_PAGE_URL.format(code_lower="test-001"))


if __name__ == "__main__":
    unittest.main()
