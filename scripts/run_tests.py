"""Run every workflow and toolbox unittest file in an isolated process."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tests = sorted((ROOT / "flowsteps").rglob("tests/test_*.py"))
    if not tests:
        print("No tests found", file=sys.stderr)
        return 1
    failures: list[Path] = []
    for test in tests:
        relative = test.relative_to(ROOT)
        print(f"\n=== {relative} ===", flush=True)
        result = subprocess.run([sys.executable, str(test)], cwd=ROOT, check=False)
        if result.returncode != 0:
            failures.append(relative)
    if failures:
        print("\nFailed test files:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"\nPASS: {len(tests)} test files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
