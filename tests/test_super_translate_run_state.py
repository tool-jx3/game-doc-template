from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def load_run_state_module():
    root = Path(__file__).resolve().parents[1]
    mod_path = root / ".claude" / "skills" / "super-translate" / "scripts" / "run_state.py"
    spec = importlib.util.spec_from_file_location("run_state_mod", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load run_state module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestRunStateScript(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_run_state_module()
        self.tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.tmp.name) / ".state"
        self.summary_file = self.state_dir / "summary.env"
        self.files_file = self.state_dir / "files.tsv"

        self.old = (
            self.mod.STATE_DIR,
            self.mod.SUMMARY_FILE,
            self.mod.FILES_FILE,
        )
        self.mod.STATE_DIR = self.state_dir
        self.mod.SUMMARY_FILE = self.summary_file
        self.mod.FILES_FILE = self.files_file

    def tearDown(self) -> None:
        self.mod.STATE_DIR, self.mod.SUMMARY_FILE, self.mod.FILES_FILE = self.old
        self.tmp.cleanup()

    def test_start_creates_state_files(self) -> None:
        result = self.mod.cmd_start(["a.md", "b.md"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["targets"], 2)
        self.assertTrue(self.summary_file.exists())
        self.assertTrue(self.files_file.exists())

        rows = self.mod.read_files_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["status"], "pending")

    def test_update_requires_start(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.mod.cmd_update(file="a.md", status="running")

    def test_update_and_end_flow(self) -> None:
        self.mod.cmd_start(["a.md", "b.md"])

        upd = self.mod.cmd_update(file="a.md", status="running", critical_fixed=1, remaining_critical=2)
        self.assertEqual(upd["status"], "running")
        self.assertEqual(upd["pending"], 2)  # pending + running

        upd2 = self.mod.cmd_update(file="a.md", status="pass", critical_fixed=2, remaining_critical=0)
        self.assertEqual(upd2["status"], "pass")
        self.assertEqual(upd2["pending"], 1)

        end = self.mod.cmd_end()
        self.assertTrue(end["ok"])

        summary = self.mod.load_summary()
        self.assertEqual(summary.active, 0)
        self.assertTrue(summary.ended_at)

    def test_status_output_contains_table(self) -> None:
        self.mod.cmd_start(["a.md"])
        self.mod.cmd_update(file="a.md", status="pass")
        text = self.mod.cmd_status()
        self.assertIn("ACTIVE=", text)
        self.assertIn("file\tstatus", text)
        self.assertIn("a.md\tpass", text)

    def test_invalid_status_raises(self) -> None:
        self.mod.cmd_start(["a.md"])
        with self.assertRaises(ValueError):
            self.mod.cmd_update(file="a.md", status="done")


if __name__ == "__main__":
    unittest.main()
