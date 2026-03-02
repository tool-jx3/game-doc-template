#!/usr/bin/env python3
"""Run init-doc handoff gate checks in one command."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


REQUIRED_FILES = [
    "glossary.json",
    "style-decisions.json",
    "chapters.json",
    "data/translation-progress.json",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run init-doc handoff gate checks.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--skip-docs-build", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def check_required_files(root: Path) -> list[str]:
    missing: list[str] = []
    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            missing.append(rel)
    return missing


def run_cmd(cmd: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def main() -> None:
    args = parse_args()
    root = args.project_root.resolve()

    report: dict[str, Any] = {
        "project_root": str(root),
        "missing_files": [],
        "checks": [],
        "ok": True,
    }

    missing = check_required_files(root)
    report["missing_files"] = missing
    if missing:
        report["ok"] = False
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print("❌ Missing required files:")
            for item in missing:
                print(f"- {item}")
        raise SystemExit(1)

    py = sys.executable
    checks = [
        [py, "scripts/validate_glossary.py"],
        [py, "scripts/term_read.py", "--fail-on-missing", "--fail-on-forbidden"],
    ]
    if not args.skip_docs_build:
        checks.append(["bun", "run", "build"])

    for cmd in checks:
        cwd = root / "docs" if cmd[0] == "bun" else root
        result = run_cmd(cmd, cwd=cwd)
        report["checks"].append(result)
        if result["returncode"] != 0:
            report["ok"] = False
            break

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        if report["ok"]:
            print("✓ init-doc handoff gate passed")
        else:
            print("❌ init-doc handoff gate failed")
            if report["checks"]:
                last = report["checks"][-1]
                print(f"Failed command: {' '.join(last['cmd'])}")
                if last["stderr"]:
                    print(last["stderr"].strip())

    if not report["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
