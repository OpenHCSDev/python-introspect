"""Prove agreement between wheel metadata and an immutable Git release ref."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from email.parser import BytesParser
from pathlib import Path
from zipfile import ZipFile


class PythonReleaseValidationError(RuntimeError):
    """A Python distribution cannot be proven to match its release ref."""


@dataclass(frozen=True)
class WheelDeclaration:
    """Name and version declared by one built wheel artifact."""

    name: str
    version: str
    path: Path

    @property
    def expected_tag(self) -> str:
        """Return the sole release tag implied by the wheel declaration."""

        return f"v{self.version}"

    @classmethod
    def from_glob(
        cls,
        repository_root: Path,
        distribution_glob: str,
    ) -> WheelDeclaration:
        """Resolve exactly one wheel and read its core metadata declaration."""

        wheel_paths = tuple(sorted(repository_root.glob(distribution_glob)))
        if len(wheel_paths) != 1 or wheel_paths[0].suffix != ".whl":
            raise PythonReleaseValidationError(
                "Release validation requires exactly one wheel matching "
                f"{distribution_glob!r}; found {len(wheel_paths)}."
            )
        wheel_path = wheel_paths[0]
        with ZipFile(wheel_path) as wheel:
            metadata_paths = tuple(
                path for path in wheel.namelist() if path.endswith(".dist-info/METADATA")
            )
            if len(metadata_paths) != 1:
                raise PythonReleaseValidationError(
                    f"Wheel {wheel_path.name} must contain exactly one METADATA file."
                )
            metadata = BytesParser().parsebytes(wheel.read(metadata_paths[0]))
        name = metadata.get("Name")
        version = metadata.get("Version")
        if not name or not version:
            raise PythonReleaseValidationError(
                f"Wheel {wheel_path.name} does not declare both Name and Version."
            )
        return cls(name=name, version=version, path=wheel_path)


@dataclass(frozen=True)
class GitReleaseRef:
    """Annotated release tag and exact commit supplied by GitHub Actions."""

    tag: str
    commit: str

    @classmethod
    def create(cls, *, tag: str, commit: str) -> GitReleaseRef:
        """Validate the external ref payload before consulting Git."""

        if re.fullmatch(r"[0-9a-f]{40}", commit) is None:
            raise PythonReleaseValidationError(
                f"Release commit must be one full lowercase SHA: {commit!r}."
            )
        if not tag:
            raise PythonReleaseValidationError("Release tag cannot be empty.")
        return cls(tag=tag, commit=commit)

    def prove(
        self,
        declaration: WheelDeclaration,
        repository_root: Path,
    ) -> None:
        """Prove tag spelling, tag kind, tag target, and checkout identity."""

        if self.tag != declaration.expected_tag:
            raise PythonReleaseValidationError(
                f"Release tag {self.tag!r} does not match "
                f"{declaration.name}=={declaration.version}; expected "
                f"{declaration.expected_tag!r}."
            )
        tag_ref = f"refs/tags/{self.tag}"
        if _run_git(repository_root, "cat-file", "-t", tag_ref) != "tag":
            raise PythonReleaseValidationError(f"Release ref {tag_ref} must be an annotated tag.")
        tag_commit = _run_git(repository_root, "rev-list", "-n", "1", tag_ref)
        if tag_commit != self.commit:
            raise PythonReleaseValidationError(
                f"Release tag {tag_ref} resolves to {tag_commit}, not {self.commit}."
            )
        checkout_commit = _run_git(repository_root, "rev-parse", "HEAD")
        if checkout_commit != self.commit:
            raise PythonReleaseValidationError(
                f"Release checkout is {checkout_commit}, not {self.commit}."
            )


def _run_git(repository_root: Path, *arguments: str) -> str:
    """Run one Git proof command and translate failure into validation failure."""

    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", None) or str(exc)
        raise PythonReleaseValidationError(
            f"Could not prove Git release ref: {detail.strip()}"
        ) from exc
    return result.stdout.strip()


def main(arguments: list[str] | None = None) -> int:
    """Validate one release artifact/ref boundary."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--distribution-glob", default="dist/*.whl")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args(arguments)
    try:
        repository_root = args.repository_root.resolve(strict=True)
        declaration = WheelDeclaration.from_glob(
            repository_root,
            args.distribution_glob,
        )
        release_ref = GitReleaseRef.create(tag=args.tag, commit=args.commit)
        release_ref.prove(declaration, repository_root)
    except (OSError, PythonReleaseValidationError) as exc:
        print(f"Python release validation failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Validated {declaration.name}=={declaration.version} from "
        f"{release_ref.tag} at {release_ref.commit}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
