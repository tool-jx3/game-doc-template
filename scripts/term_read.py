#!/usr/bin/env python3
"""Read glossary and validate terminology consistency against docs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from _term_lib import (
    DEFAULT_GLOSSARY,
    DEFAULT_GLOSSARY_SCHEMA,
    INDEX_CACHE,
    PROJECT_ROOT,
    build_corpus,
    count_terms_batch,
    extract_candidates,
    is_managed_term,
    load_glossary,
    load_json,
    resolve_root,
    save_json,
)
from jsonschema import Draft202012Validator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read and validate glossary terms.")
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument("--schema", type=Path, default=DEFAULT_GLOSSARY_SCHEMA)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--reindex", action="store_true")
    parser.add_argument("--unknown-min-frequency", type=int, default=3)
    parser.add_argument("--unknown-limit", type=int, default=20)
    parser.add_argument("--fail-on-forbidden", action="store_true")
    parser.add_argument("--fail-on-missing", action="store_true")
    parser.add_argument("--no-schema-validate", action="store_true")
    return parser.parse_args()


def load_or_build_index(root: Path, force: bool) -> tuple[dict[str, str], str]:
    corpus, fingerprint = build_corpus(root)
    if force:
        save_json(INDEX_CACHE, {"fingerprint": fingerprint, "corpus": corpus})
        return corpus, fingerprint

    cache = load_json(INDEX_CACHE, {})
    if cache.get("fingerprint") == fingerprint and isinstance(cache.get("corpus"), dict):
        return cache["corpus"], fingerprint

    save_json(INDEX_CACHE, {"fingerprint": fingerprint, "corpus": corpus})
    return corpus, fingerprint


def main() -> None:
    args = parse_args()
    args.root = resolve_root(args.root)
    glossary = load_glossary(args.glossary)
    schema_errors: list[str] = []
    if not args.no_schema_validate:
        schema = load_json(args.schema, None)
        if schema is None:
            schema_errors.append(f"Schema file not found: {args.schema}")
        else:
            validator = Draft202012Validator(schema)
            for error in sorted(validator.iter_errors(glossary), key=lambda e: list(e.path)):
                path = ".".join(str(p) for p in error.path) or "<root>"
                schema_errors.append(f"{path}: {error.message}")
    corpus, fingerprint = load_or_build_index(args.root, force=args.reindex)

    managed_terms: list[tuple[str, dict[str, Any]]] = []
    for term, entry in glossary.items():
        if term == "_meta":
            continue
        if is_managed_term(term, entry):
            managed_terms.append((term, entry))

    managed_terms.sort(key=lambda x: x[0].lower())

    missing_terms: list[dict[str, Any]] = []
    term_usage: list[dict[str, Any]] = []
    forbidden_hits: list[dict[str, Any]] = []

    # Collect all terms + forbidden variants for a single batch pass.
    all_search_terms: list[str] = []
    forbidden_map: dict[str, str] = {}  # forbidden_variant -> parent_term
    for term, entry in managed_terms:
        all_search_terms.append(term)
        for forbidden in entry.get("forbidden", []):
            all_search_terms.append(forbidden)
            forbidden_map[forbidden] = term

    batch_results = count_terms_batch(corpus, all_search_terms)

    for term, _entry in managed_terms:
        total, files = batch_results.get(term, (0, {}))
        term_usage.append({"term": term, "count": total, "files": files})
        if total == 0:
            missing_terms.append({"term": term})

    for forbidden, parent_term in forbidden_map.items():
        bad_total, bad_files = batch_results.get(forbidden, (0, {}))
        if bad_total > 0:
            forbidden_hits.append(
                {
                    "term": parent_term,
                    "forbidden": forbidden,
                    "count": bad_total,
                    "files": bad_files,
                }
            )

    known_keys = {k.lower() for k in glossary.keys() if k != "_meta"}
    unknown = []
    for item in extract_candidates(corpus, min_frequency=args.unknown_min_frequency):
        if item["normalized"] in known_keys:
            continue
        unknown.append(item)
        if len(unknown) >= args.unknown_limit:
            break

    report = {
        "root": str(args.root.relative_to(PROJECT_ROOT) if args.root.is_absolute() else args.root),
        "fingerprint": fingerprint,
        "schema_errors": schema_errors,
        "managed_term_count": len(managed_terms),
        "term_usage": term_usage,
        "missing_terms": missing_terms,
        "forbidden_hits": forbidden_hits,
        "unknown_candidates": unknown,
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(f"已管理術語: {report['managed_term_count']}")
    print(f"Schema 錯誤: {len(report['schema_errors'])}")
    print(f"缺少使用: {len(report['missing_terms'])}")
    print(f"禁用詞命中: {len(report['forbidden_hits'])}")
    print("")

    if report["schema_errors"]:
        print("Schema Errors")
        for err in report["schema_errors"]:
            print(f"- {err}")
        print("")

    if report["missing_terms"]:
        print("Missing Terms")
        for item in report["missing_terms"]:
            print(f"- {item['term']}")
        print("")

    if report["forbidden_hits"]:
        print("Forbidden Hits")
        for item in report["forbidden_hits"]:
            print(f"- {item['forbidden']} (for {item['term']}): {item['count']}")
        print("")

    print("Top Unknown Candidates")
    for item in report["unknown_candidates"]:
        print(f"- {item['term']} ({item['count']})")

    should_fail = bool(report["schema_errors"])
    if args.fail_on_forbidden and report["forbidden_hits"]:
        should_fail = True
    if args.fail_on_missing and report["missing_terms"]:
        should_fail = True
    if should_fail:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
