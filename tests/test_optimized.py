import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [sys.executable, *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_run_v2_dry_run() -> None:
    result = run_cli("run_v2.py", "油价会涨吗？", "--dry-run")
    assert "asset: oil" in result.stdout


def test_run_v2_new_cleaner_dry_run() -> None:
    result = run_cli("run_v2.py", "美联储会不会降息？", "--dry-run", "--new-cleaner")
    assert "极速决策完成" in result.stdout
