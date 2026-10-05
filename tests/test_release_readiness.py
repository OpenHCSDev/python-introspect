"""Readiness checks consume the repository's declared project metadata."""

import runpy
from pathlib import Path

import pytest


CHECKS = runpy.run_path(str(Path(__file__).parents[1] / "scripts/verify_release_ready.py"))
PROJECT = (Path(__file__).parents[1] / "pyproject.toml").read_text()


def test_actual_project_declaration_is_release_ready(monkeypatch):
    monkeypatch.chdir(Path(__file__).parents[1])
    assert CHECKS["check_pyproject_toml"]()


@pytest.mark.parametrize("name", ('name = "invalid name"', ""))
def test_missing_or_invalid_project_name_is_rejected(tmp_path, monkeypatch, name):
    (tmp_path / "pyproject.toml").write_text(PROJECT.replace('name = "python-introspect"', name))
    monkeypatch.chdir(tmp_path)
    assert not CHECKS["check_pyproject_toml"]()
