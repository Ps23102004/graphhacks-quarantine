"""Tests for deployment configuration, Dockerfile, and Compose specification."""
from __future__ import annotations

import subprocess
from pathlib import Path
import yaml
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO_ROOT / "deploy" / "docker-compose.yml"
DOCKERFILE = REPO_ROOT / "deploy" / "Dockerfile"


def test_compose_config_validates():
    res = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config", "--quiet"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert res.returncode == 0, res.stderr


def test_compose_spec_rules():
    spec = yaml.safe_load(COMPOSE_FILE.read_text())
    services = spec["services"]

    # 1. No hardcoded container_name
    for name, s in services.items():
        assert "container_name" not in s, f"Service {name} must not hardcode container_name"

    # 2. FalkorDB configuration
    falkor = services["falkordb"]
    assert "falkordb/falkordb:6.0.2@sha256:107455e862a824e45e8e9f5a7fbfdf5e00a08b14e13eae2577c72fd9e3f59ba6" in falkor["image"]
    assert "ports" not in falkor, "FalkorDB service must not publish unauthenticated ports to host"
    env = dict(e.split("=", 1) for e in falkor["environment"])
    assert env.get("BROWSER") == "0"
    assert "--appendonly yes" in env.get("REDIS_ARGS", "")
    assert any("/var/lib/falkordb/data" in v for v in falkor["volumes"])

    # 3. Web service configuration
    web = services["web"]
    assert web["build"]["context"] == ".."
    assert web["build"]["dockerfile"] == "deploy/Dockerfile"
    ports = web["ports"]
    assert any(p.startswith("127.0.0.1:") for p in ports), "Web port must bind to loopback 127.0.0.1"


def test_dockerfile_spec_rules():
    content = DOCKERFILE.read_text()
    assert "python:3.13-slim-bookworm@sha256:5024f48ba9441d4b13a95d3945abc6365538e3a31109833367a1923523c6efed" in content
    assert "uv==0.11.23" in content
    assert "uv sync --frozen" in content
    assert "--host" in content and "0.0.0.0" in content
