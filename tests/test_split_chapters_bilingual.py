import subprocess, json
from pathlib import Path

def test_split_chapters_bilingual_output_dir(tmp_path):
    """chapters.json with mode=bilingual should write to bilingual/ subdir."""
    source = tmp_path / "source.md"
    source.write_text("<!-- page 1 -->\n# Test\n\nHello world.\n")
    out_dir = tmp_path / "docs" / "src" / "content" / "docs"
    cfg = {
        "source": str(source),
        "output_dir": str(out_dir),
        "mode": "bilingual",
        "chapters": {
            "rules": {
                "title": "規則",
                "order": 1,
                "files": {
                    "index": {
                        "title": "規則總覽",
                        "description": "test",
                        "pages": [1, 1]
                    }
                }
            }
        }
    }
    cfg_file = tmp_path / "chapters.json"
    cfg_file.write_text(json.dumps(cfg))
    result = subprocess.run(
        ["uv", "run", "python", "scripts/split_chapters.py", "--config", str(cfg_file)],
        capture_output=True, text=True, cwd="/Users/weihung/projects/game-doc-template"
    )
    assert result.returncode == 0, result.stderr
    bilingual_dir = out_dir / "bilingual" / "rules"
    assert bilingual_dir.exists(), f"Expected {bilingual_dir} to exist"
