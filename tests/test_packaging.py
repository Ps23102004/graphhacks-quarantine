"""Tests for packaging, wheel building, and data files distribution."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_wheel_build_and_contents():
    # Build wheel with uv
    res = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(REPO_ROOT / "dist")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert res.returncode == 0, res.stderr

    wheels = list((REPO_ROOT / "dist").glob("quarantine-*.whl"))
    assert wheels, "No wheel file found in dist/"
    wheel_path = sorted(wheels, key=os.path.getmtime)[-1]

    with zipfile.ZipFile(wheel_path) as z:
        names = z.namelist()
        # Verify quarantine package
        assert "quarantine/__init__.py" in names
        assert "quarantine/mcp_server.py" in names
        # Verify web package and data assets
        assert "web/__init__.py" in names
        assert "web/server.py" in names
        assert "web/index.html" in names
        # Verify fixture.yaml under share/quarantine
        assert any(n.endswith("share/quarantine/fixture.yaml") for n in names)


def test_install_wheel_in_isolated_venv_outside_checkout():
    wheels = list((REPO_ROOT / "dist").glob("quarantine-*.whl"))
    if not wheels:
        subprocess.run(["uv", "build", "--wheel"], cwd=REPO_ROOT, check=True)
        wheels = list((REPO_ROOT / "dist").glob("quarantine-*.whl"))
    wheel_path = sorted(wheels, key=os.path.getmtime)[-1].resolve()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        venv_dir = tmp_path / "venv"

        # Create isolated venv
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        venv_python = venv_dir / "bin" / "python"

        # Install wheel
        subprocess.run([str(venv_python), "-m", "pip", "install", "--no-cache-dir", str(wheel_path)], check=True)

        # Run verification script from tmpdir (completely outside checkout)
        check_script = """
import sys
from pathlib import Path
import quarantine
import web.server

# Verify web assets are present in package
web_dir = Path(web.server.__file__).resolve().parent
assert (web_dir / "index.html").exists(), "index.html missing from installed web package"

# Verify fixture.yaml is in sys.prefix / share / quarantine
prefix_fixture = Path(sys.prefix) / "share" / "quarantine" / "fixture.yaml"
assert prefix_fixture.exists(), f"fixture.yaml missing at {prefix_fixture}"

print("Installed wheel verified successfully outside checkout")
"""
        proc = subprocess.run(
            [str(venv_python), "-c", check_script],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, proc.stderr
        assert "Installed wheel verified successfully" in proc.stdout
