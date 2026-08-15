#!/usr/bin/env python3
"""
Pytest Hook

Runs pytest after Python file changes to catch test failures early.
Skips if no test files exist to avoid unnecessary delays.
"""

import json
import sys
import subprocess
from pathlib import Path


def has_test_files() -> bool:
    """Check if scripts/tests contains any test files."""
    tests_dir = Path.cwd() / "scripts" / "tests"
    if not tests_dir.is_dir():
        return False
    return any(tests_dir.glob("test_*.py"))


def is_python_file_change(data: dict) -> bool:
    """Check if the tool change affects Python files in scripts/."""
    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    # Only check Write and Edit tools
    if tool_name not in ['Write', 'Edit']:
        return False

    file_path = tool_input.get('file_path', '')
    if not file_path:
        return False

    if not file_path.endswith('.py'):
        return False
    normalized = file_path.replace('\\', '/')
    return '/scripts/' in normalized or normalized.startswith('scripts/')


def run_pytest() -> tuple[bool, str]:
    """
    Run pytest and return (success, output).
    Returns (True, "") if tests pass or no tests exist.
    """
    try:
        # Run pytest with timeout and capture output
        result = subprocess.run(
            ['uv', 'run', 'pytest', '-v', '--tb=short', '-x'],
            capture_output=True,
            text=True,
            timeout=90,  # 90 second timeout (cold uv-sync run measured ~39s on 365 tests)
            cwd=Path.cwd()
        )

        if result.returncode == 0:
            return True, ""
        else:
            # Extract relevant error information
            error_lines = []
            output_lines = result.stdout.split('\n') + result.stderr.split('\n')

            for line in output_lines:
                # Include FAILED lines and assertion errors
                if any(marker in line for marker in ['FAILED', 'ERRORS', 'AssertionError', '===', 'assert']):
                    if line.strip():
                        error_lines.append(line.strip())

            # Limit output to first 10 lines
            limited_output = error_lines[:10]
            if len(error_lines) > 10:
                limited_output.append(f"... and {len(error_lines) - 10} more errors")

            return False, '\n'.join(limited_output)

    except subprocess.TimeoutExpired:
        return False, "Pytest timeout (90s) - tests may be hanging or too slow"
    except FileNotFoundError:
        return False, "uv not found - cannot run pytest"
    except Exception as e:
        return False, f"Pytest execution failed: {str(e)}"


def main():
    """Main hook execution."""
    try:
        # Read tool usage data from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            sys.exit(0)

        try:
            data = json.loads(input_data)
        except json.JSONDecodeError:
            # Not JSON data, ignore
            sys.exit(0)

        # Check if this affects Python files
        if not is_python_file_change(data):
            sys.exit(0)

        # Skip if no test files exist
        if not has_test_files():
            sys.exit(0)

        # Run pytest
        success, error_output = run_pytest()

        if not success:
            # Block the operation due to test failures
            error_message = "🧪 Pytest failed - Fix failing tests before proceeding:\n\n"
            error_message += error_output
            error_message += "\n\n💡 Run 'uv run pytest -v' to see full test output."

            print(error_message, file=sys.stderr)
            sys.exit(2)  # Block the operation

        # Tests passed
        sys.exit(0)

    except Exception as e:
        # Hook failed, but don't block the operation
        print(f"Pytest hook error: {e}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()