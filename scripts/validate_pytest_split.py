from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _collect(marker: str | None = None) -> list[str]:
    command = [sys.executable, "-m", "pytest", "--collect-only", "-q"]
    if marker:
        command.extend(["-m", marker])
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    node_ids: list[str] = []
    for line in completed.stdout.splitlines():
        value = line.strip()
        if not value or not value.startswith("tests/"):
            continue
        if value.endswith(".py") or "::" in value:
            node_ids.append(value)
    return node_ids


def main() -> int:
    all_tests = _collect()
    serial_tests = _collect("serial")
    parallel_tests = _collect("not serial")

    if len(serial_tests) + len(parallel_tests) != len(all_tests):
        print(
            "serial/non-serial split does not cover full collection exactly once:",
            f"total={len(all_tests)}",
            f"parallel={len(parallel_tests)}",
            f"serial={len(serial_tests)}",
            file=sys.stderr,
        )
        return 1

    print(
        "split validated:",
        f"total={len(all_tests)}",
        f"parallel={len(parallel_tests)}",
        f"serial={len(serial_tests)}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
