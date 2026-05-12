from pathlib import Path
import re
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FrontendUiTests(unittest.TestCase):
    def test_bootstrap_fetches_nas_file_names_when_available(self):
        html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("async function refreshNasFiles()", html)
        self.assertIn('fetch("/nas/files")', html)
        self.assertRegex(html, r"if \(nasAvailable\) \{\s+await refreshNasFiles\(\);")

    def test_render_file_list_marks_nas_name_matches_uploaded(self):
        html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("const nasFileNames = new Set();", html)
        self.assertIn("if (nasFileNames.has(file))", html)
        self.assertIn('nasBtn.textContent = "✓ 已上傳";', html)
        self.assertIn("nasBtn.disabled = true;", html)

    def test_successful_nas_upload_keeps_uploaded_button_state(self):
        html = (PROJECT_ROOT / "index.html").read_text(encoding="utf-8")
        match = re.search(
            r"if \(resp\.ok\) \{(?P<body>.*?)\n\s+\} else \{",
            html,
            re.DOTALL,
        )

        self.assertIsNotNone(match)
        success_body = match.group("body")
        self.assertIn('btn.textContent = "✓ 已上傳";', success_body)
        self.assertIn("btn.disabled = true;", success_body)
        self.assertNotIn("setTimeout", success_body)
        self.assertNotIn('btn.textContent = "傳到 NAS";', success_body)


if __name__ == "__main__":
    unittest.main()
