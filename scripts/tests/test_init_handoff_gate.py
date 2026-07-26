from __future__ import annotations

import init_handoff_gate as gate


def test_missing_bun_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(gate.shutil, "which", lambda _cmd: None)
    result = gate.check_bun_available()
    assert result is False


def test_run_cmd_uses_utf8(monkeypatch):
    captured = {}

    def fake_run(cmd, cwd, capture_output, text, encoding):
        captured["encoding"] = encoding

        class P:
            returncode = 0
            stdout = ""
            stderr = ""

        return P()

    monkeypatch.setattr(gate.subprocess, "run", fake_run)
    gate.run_cmd(["echo"], cwd=gate.PROJECT_ROOT)
    assert captured["encoding"] == "utf-8"
