from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from zipfile import ZipFile

import pytest

ACTION_SCRIPT = (
    Path(__file__).parents[1]
    / ".github"
    / "actions"
    / "validate-python-release"
    / "validate_python_release.py"
)


def _load_action() -> ModuleType:
    spec = importlib.util.spec_from_file_location("validate_python_release", ACTION_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _git(repository: Path, *arguments: str) -> str:
    return subprocess.run(
        ("git", *arguments),
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _release_repository(tmp_path: Path, tag: str, *, annotated: bool = True) -> str:
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "release@example.test")
    _git(tmp_path, "config", "user.name", "Release Test")
    (tmp_path / "tracked.txt").write_text("release\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-m", "Release candidate")
    if annotated:
        _git(tmp_path, "tag", "-a", tag, "-m", tag)
    else:
        _git(tmp_path, "tag", tag)
    return _git(tmp_path, "rev-parse", "HEAD")


def _wheel(tmp_path: Path, version: str = "1.2.3") -> None:
    distribution = tmp_path / "dist" / f"demo_package-{version}-py3-none-any.whl"
    distribution.parent.mkdir()
    with ZipFile(distribution, "w") as wheel:
        wheel.writestr(
            f"demo_package-{version}.dist-info/METADATA",
            "Metadata-Version: 2.1\n" "Name: demo-package\n" f"Version: {version}\n",
        )


def test_action_accepts_one_matching_annotated_release(tmp_path: Path) -> None:
    action = _load_action()
    commit = _release_repository(tmp_path, "v1.2.3")
    _wheel(tmp_path)

    assert (
        action.main(
            [
                "--repository-root",
                str(tmp_path),
                "--tag",
                "v1.2.3",
                "--commit",
                commit,
            ]
        )
        == 0
    )


@pytest.mark.parametrize(
    ("tag", "version", "annotated"),
    [
        ("v1.2.4", "1.2.3", True),
        ("v1.2.3", "1.2.3", False),
    ],
)
def test_action_rejects_mismatched_or_lightweight_tags(
    tmp_path: Path,
    tag: str,
    version: str,
    annotated: bool,
) -> None:
    action = _load_action()
    commit = _release_repository(tmp_path, tag, annotated=annotated)
    _wheel(tmp_path, version)

    assert (
        action.main(
            [
                "--repository-root",
                str(tmp_path),
                "--tag",
                tag,
                "--commit",
                commit,
            ]
        )
        == 1
    )


def test_action_rejects_a_commit_other_than_the_tag_target(tmp_path: Path) -> None:
    action = _load_action()
    _release_repository(tmp_path, "v1.2.3")
    _wheel(tmp_path)
    (tmp_path / "tracked.txt").write_text("later\n", encoding="utf-8")
    _git(tmp_path, "add", "tracked.txt")
    _git(tmp_path, "commit", "-m", "Later commit")
    later_commit = _git(tmp_path, "rev-parse", "HEAD")

    assert (
        action.main(
            [
                "--repository-root",
                str(tmp_path),
                "--tag",
                "v1.2.3",
                "--commit",
                later_commit,
            ]
        )
        == 1
    )
