#!/usr/bin/env python3
"""Batch-calculate corpus counts for all candidate/glossary terms in one pass."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from _term_lib import (
    CAL_CACHE,
    CANDIDATE_CACHE,
    DEFAULT_GLOSSARY,
    build_corpus,
    canonical_term_key,
    count_terms_batch,
    ensure_cache_dir,
    is_managed_term,
    load_glossary,
    load_json,
    resolve_root,
    sample_contexts,
    save_json,
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch-calculate --cal for all candidate/glossary terms in one corpus scan."
    )
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--glossary", type=Path, default=DEFAULT_GLOSSARY)
    parser.add_argument(
        "--from",
        dest="source",
        choices=["candidates", "glossary", "both"],
        default="both",
        help="Which terms to calculate (default: both).",
    )
    parser.add_argument(
        "--min-frequency",
        type=int,
        default=2,
        help="Minimum count threshold; terms below this are skipped (default: 2).",
    )
    parser.add_argument(
        "--skip-managed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip already-managed (approved/is_term) glossary entries; use --no-skip-managed to include them.",
    )
    parser.add_argument(
        "--context-limit",
        type=int,
        default=5,
        help="Max context snippets to collect per term (default: 5).",
    )
    parser.add_argument("--json", action="store_true", help="Print full results JSON to stdout.")
    parser.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    return parser.parse_args()


def collect_terms(args: argparse.Namespace, glossary: dict) -> list[str]:
    terms: set[str] = set()

    if args.source in ("candidates", "both"):
        cache = load_json(CANDIDATE_CACHE, None)
        if cache is None:
            print("⚠️  候選術語快取不存在，請先執行 term_generate.py", file=sys.stderr)
        else:
            for c in cache.get("candidates", []):
                term = canonical_term_key(c["term"])
                if term:
                    terms.add(term)

    if args.source in ("glossary", "both"):
        for key, entry in glossary.items():
            if key == "_meta":
                continue
            if args.skip_managed and is_managed_term(key, entry):
                continue
            term = canonical_term_key(key)
            if term:
                terms.add(term)

    return sorted(terms)


def main() -> None:
    args = parse_args()
    args.root = resolve_root(args.root)
    glossary = load_glossary(args.glossary)
    ensure_cache_dir()

    terms = collect_terms(args, glossary)
    if not terms:
        print("❌ 沒有找到需要計算的術語。", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(f"📊 掃描語料庫：{args.root.relative_to(Path.cwd()) if args.root.is_relative_to(Path.cwd()) else args.root}")
        print(f"🔢 待計算術語數：{len(terms)}")

    corpus, fingerprint = build_corpus(args.root)

    if not args.quiet:
        print(f"📄 語料庫檔案數：{len(corpus)}，fingerprint：{fingerprint[:12]}…")
        print("⏳ 批次計算中（單次掃描）…")

    batch_results = count_terms_batch(corpus, terms)

    # Load existing cache to preserve managed-term entries.
    cache = load_json(CAL_CACHE, {"terms": {}})
    cache.setdefault("terms", {})

    calculated_at = now_iso()
    written = 0
    skipped_low = 0

    for term in terms:
        total, per_file = batch_results.get(term, (0, {}))
        if total < args.min_frequency:
            skipped_low += 1
            continue

        contexts = sample_contexts(corpus, term, limit=args.context_limit)
        payload = {
            "term": term,
            "managed": False,
            "count": total,
            "files": per_file,
            "contexts": contexts,
            "fingerprint": fingerprint,
            "calculated_at": calculated_at,
        }
        cache["terms"][term] = payload
        written += 1

    save_json(CAL_CACHE, cache)

    if not args.quiet:
        print(f"✅ 完成：寫入 {written} 筆，略過低頻 {skipped_low} 筆（< {args.min_frequency}）")
        print(f"💾 快取路徑：{CAL_CACHE}")

    if args.json:
        output = {t: cache["terms"][t] for t in terms if t in cache["terms"]}
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
