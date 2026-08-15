from __future__ import annotations

from bilingual_prep import build_bilingual_draft, merge_soft_linebreaks

PLACEHOLDER = "<!-- TODO: 翻譯 -->"


def test_merge_soft_linebreaks_english_joins_with_space():
    assert merge_soft_linebreaks("line one\nline two") == "line one line two"


def test_merge_soft_linebreaks_chinese_joins_without_space():
    assert merge_soft_linebreaks("第一行\n第二行") == "第一行第二行"


def test_merge_soft_linebreaks_preserves_paragraph_boundary():
    assert merge_soft_linebreaks("para one\n\npara two") == "para one\n\npara two"


def test_build_bilingual_draft_plain_paragraph():
    result = build_bilingual_draft("When a character attacks, they roll dice.")
    assert PLACEHOLDER in result
    assert "> When a character attacks, they roll dice." in result


def test_build_bilingual_draft_heading_kept_as_is():
    result = build_bilingual_draft("## Combat\n\nSome rules here.")
    lines = result.splitlines()
    assert lines[0] == "## Combat"
    # Only the plain paragraph gets a placeholder, never the heading.
    assert result.count(PLACEHOLDER) == 1
    assert "> Some rules here." in result


def test_build_bilingual_draft_code_block_no_placeholder():
    result = build_bilingual_draft("Text before.\n\n```\ncode here\n```\n\nText after.")
    # Only "Text before." and "Text after." are translatable.
    assert result.count(PLACEHOLDER) == 2
    assert "```\ncode here\n```" in result
    assert "> code here" not in result


def test_build_bilingual_draft_table_no_placeholder():
    result = build_bilingual_draft("| A | B |\n|---|---|\n| 1 | 2 |")
    assert PLACEHOLDER not in result
    assert "| A | B |" in result


def test_build_bilingual_draft_preserves_frontmatter():
    result = build_bilingual_draft("---\ntitle: Combat\n---\n\nSome rules here.")
    assert result.startswith("---\ntitle: Combat\n---")
    assert result.count(PLACEHOLDER) == 1
