from __future__ import annotations

import subprocess
from pathlib import Path


def test_import_api_app():
    from app import api  # noqa: F401


def test_compile_app_module():
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        ["python3", "-m", "compileall", "apps/api/app"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
