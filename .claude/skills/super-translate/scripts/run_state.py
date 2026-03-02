#!/usr/bin/env python3
"""Track super-translate runtime state per target file."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
STATE_DIR = SKILL_DIR / ".state"
SUMMARY_FILE = STATE_DIR / "summary.env"
FILES_FILE = STATE_DIR / "files.tsv"

FILES_HEADER = [
    "file",
    "status",
    "critical_fixed",
    "minor_fixed",
    "remaining_critical",
    "updated_at",
]
VALID_STATUS = {"running", "pass", "blocked", "failed"}


@dataclass
class Summary:
    active: int = 0
    pending_count: int = 0
    unresolved_critical_total: int = 0
    started_at: str = ""
    ended_at: str = ""
    updated_at: str = ""


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def parse_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value


def load_summary() -> Summary:
    summary = Summary()
    if not SUMMARY_FILE.exists():
        return summary

    for line in SUMMARY_FILE.read_text(encoding="utf-8").splitlines():
        if not line or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        value = parse_env_value(raw)
        if key == "ACTIVE":
            summary.active = int(value or 0)
        elif key == "PENDING_COUNT":
            summary.pending_count = int(value or 0)
        elif key == "UNRESOLVED_CRITICAL_TOTAL":
            summary.unresolved_critical_total = int(value or 0)
        elif key == "STARTED_AT":
            summary.started_at = value
        elif key == "ENDED_AT":
            summary.ended_at = value
        elif key == "UPDATED_AT":
            summary.updated_at = value
    return summary


def write_summary(*, active: int, pending: int, unresolved: int, started: str, ended: str) -> None:
    SUMMARY_FILE.write_text(
        "\n".join(
            [
                f"ACTIVE={active}",
                f"PENDING_COUNT={pending}",
                f"UNRESOLVED_CRITICAL_TOTAL={unresolved}",
                f"STARTED_AT='{started}'",
                f"ENDED_AT='{ended}'",
                f"UPDATED_AT='{now_utc()}'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def read_files_rows() -> list[dict[str, str]]:
    if not FILES_FILE.exists():
        return []
    with FILES_FILE.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader)


def write_files_rows(rows: list[dict[str, Any]]) -> None:
    with FILES_FILE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FILES_HEADER, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FILES_HEADER})


def recalculate_counters(rows: list[dict[str, str]]) -> tuple[int, int]:
    pending = 0
    unresolved = 0
    for row in rows:
        status = row.get("status", "")
        if status in {"pending", "running"}:
            pending += 1
        try:
            unresolved += int(row.get("remaining_critical", "0") or 0)
        except ValueError:
            unresolved += 0
    return pending, unresolved


def cmd_start(targets: list[str]) -> dict[str, Any]:
    if not targets:
        raise ValueError("start requires at least one target")
    ensure_state_dir()
    ts = now_utc()

    rows: list[dict[str, Any]] = []
    for target in targets:
        rows.append(
            {
                "file": target,
                "status": "pending",
                "critical_fixed": 0,
                "minor_fixed": 0,
                "remaining_critical": 0,
                "updated_at": ts,
            }
        )
    write_files_rows(rows)
    write_summary(active=1, pending=len(rows), unresolved=0, started=ts, ended="")
    return {"ok": True, "action": "start", "targets": len(rows)}


def cmd_update(
    *,
    file: str,
    status: str,
    critical_fixed: int = 0,
    minor_fixed: int = 0,
    remaining_critical: int = 0,
) -> dict[str, Any]:
    if not file or not status:
        raise ValueError("update requires --file and --status")
    if status not in VALID_STATUS:
        raise ValueError(f"invalid status: {status}")

    ensure_state_dir()
    if not FILES_FILE.exists():
        raise FileNotFoundError("run-state not initialized; call start first")

    ts = now_utc()
    rows = read_files_rows()
    updated = False
    for row in rows:
        if row.get("file") == file:
            row.update(
                {
                    "status": status,
                    "critical_fixed": str(critical_fixed),
                    "minor_fixed": str(minor_fixed),
                    "remaining_critical": str(remaining_critical),
                    "updated_at": ts,
                }
            )
            updated = True
            break

    if not updated:
        rows.append(
            {
                "file": file,
                "status": status,
                "critical_fixed": str(critical_fixed),
                "minor_fixed": str(minor_fixed),
                "remaining_critical": str(remaining_critical),
                "updated_at": ts,
            }
        )

    write_files_rows(rows)

    summary = load_summary()
    pending, unresolved = recalculate_counters(rows)
    write_summary(
        active=1,
        pending=pending,
        unresolved=unresolved,
        started=summary.started_at or ts,
        ended=summary.ended_at,
    )

    return {
        "ok": True,
        "action": "update",
        "file": file,
        "status": status,
        "pending": pending,
        "unresolved_critical_total": unresolved,
    }


def cmd_end() -> dict[str, Any]:
    ensure_state_dir()
    summary = load_summary()
    rows = read_files_rows()
    pending, unresolved = recalculate_counters(rows)
    ts = now_utc()
    write_summary(
        active=0,
        pending=pending,
        unresolved=unresolved,
        started=summary.started_at or ts,
        ended=ts,
    )
    return {"ok": True, "action": "end"}


def cmd_status() -> str:
    summary = load_summary()
    lines = [
        f"ACTIVE={summary.active}",
        f"PENDING_COUNT={summary.pending_count}",
        f"UNRESOLVED_CRITICAL_TOTAL={summary.unresolved_critical_total}",
        f"STARTED_AT={summary.started_at}",
        f"ENDED_AT={summary.ended_at}",
        f"UPDATED_AT={summary.updated_at}",
    ]

    if FILES_FILE.exists():
        lines.append("")
        lines.extend(FILES_FILE.read_text(encoding="utf-8").splitlines())
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Track super-translate run state.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    start = sub.add_parser("start")
    start.add_argument("--targets", nargs="+", required=True)

    update = sub.add_parser("update")
    update.add_argument("--file", required=True)
    update.add_argument("--status", required=True)
    update.add_argument("--critical-fixed", type=int, default=0)
    update.add_argument("--minor-fixed", type=int, default=0)
    update.add_argument("--remaining-critical", type=int, default=0)

    sub.add_parser("end")
    sub.add_parser("status")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.cmd == "start":
            result = cmd_start(args.targets)
            print(json.dumps(result, ensure_ascii=False))
        elif args.cmd == "update":
            result = cmd_update(
                file=args.file,
                status=args.status,
                critical_fixed=args.critical_fixed,
                minor_fixed=args.minor_fixed,
                remaining_critical=args.remaining_critical,
            )
            print(json.dumps(result, ensure_ascii=False))
        elif args.cmd == "end":
            print(json.dumps(cmd_end(), ensure_ascii=False))
        elif args.cmd == "status":
            print(cmd_status())
        else:
            raise ValueError(f"unknown command: {args.cmd}")
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
