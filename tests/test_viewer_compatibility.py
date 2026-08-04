"""Viewer compatibility regression tests."""
import unittest
from pathlib import Path


APP_JS = Path(__file__).resolve().parents[1] / "viewer" / "assets" / "app.js"


class TestViewerCompatibility(unittest.TestCase):
    def test_app_avoids_nullish_coalescing_for_chrome_74(self):
        source = APP_JS.read_text(encoding="utf-8")
        self.assertEqual(source.count("??"), 0, "Chrome 74 cannot parse nullish coalescing")


if __name__ == "__main__":
    unittest.main()
