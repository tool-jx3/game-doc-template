#!/usr/bin/env python3
"""Merge multiple chapters_<name>.json files into a single chapters.json."""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from split_chapters import normalize_files

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_merge(configs: list[dict]) -> None:
    slugs: list[str] = []
    orders: list[int] = []
    for cfg in configs:
        slug = cfg["slug"]
        if slug in slugs:
            raise ValueError(f"Duplicate slug: '{slug}'")
        slugs.append(slug)
        order = cfg.get("order")
        if order is not None:
            if order in orders:
                print(f"⚠ Warning: duplicate order {order} (slug '{slug}' conflicts with earlier entry)", file=sys.stderr)
            orders.append(order)


def merge_configs(configs, *, mode_override=None, output_dir_override=None):
    first = configs[0]
    result = {
        "output_dir": output_dir_override or first.get("output_dir", "docs/src/content/docs"),
        "mode": mode_override or first.get("mode", "zh_only"),
        "chapters": {},
    }
    if "images" in first:
        result["images"] = first["images"]
    for cfg in configs:
        slug = cfg["slug"]
        chapter = {"source": cfg["source"], "title": cfg["title"], "order": cfg["order"]}
        original_chapters = cfg.get("chapters", {})
        chapter["files"] = {}
        for ch_key, ch_val in original_chapters.items():
            chapter["files"][ch_key] = ch_val
        chapter["files"] = normalize_files(chapter["files"])
        if "clean_patterns" in cfg:
            chapter["clean_patterns"] = cfg["clean_patterns"]
        if "images" in cfg:
            chapter["images"] = cfg["images"]
        result["chapters"][slug] = chapter
    return result


def expand_paths(patterns):
    paths = []
    for pattern in patterns:
        expanded = glob.glob(pattern)
        if expanded:
            for p in expanded:
                path = Path(p)
                if path not in paths:
                    paths.append(path)
        else:
            path = Path(pattern)
            if path not in paths:
                paths.append(path)
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description="Merge multiple chapters_<name>.json into chapters.json")
    parser.add_argument("inputs", nargs="+", help="Input JSON files or glob patterns")
    parser.add_argument("-o", "--output", default="chapters.json", help="Output path")
    parser.add_argument("--mode", help="Override mode")
    parser.add_argument("--output-dir", help="Override output_dir")
    args = parser.parse_args()
    input_paths = expand_paths(args.inputs)
    if not input_paths:
        print("❌ No input files found", file=sys.stderr)
        raise SystemExit(1)
    configs = []
    for path in input_paths:
        if not path.exists():
            print(f"❌ File not found: {path}", file=sys.stderr)
            raise SystemExit(1)
        configs.append(load_json(path))
    validate_merge(configs)
    result = merge_configs(configs, mode_override=args.mode, output_dir_override=args.output_dir)
    for slug, chapter in result["chapters"].items():
        files = chapter.get("files", {})
        has_index = any(k == "index" and "pages" in v for k, v in files.items())
        if not has_index:
            print(f"⚠ Warning: chapter '{slug}' has no 'index' leaf node (homepage link may 404)", file=sys.stderr)
    output_path = Path(args.output)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ Merged {len(configs)} configs → {output_path}")
    for slug, chapter in result["chapters"].items():
        print(f"  /{slug}/ → {chapter['title']} (source: {chapter['source']})")


if __name__ == "__main__":
    main()
