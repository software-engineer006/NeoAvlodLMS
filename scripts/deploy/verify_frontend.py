"""Verify the committed frontend source and complete asset sets using only stdlib."""

import hashlib
import json
import sys
from pathlib import Path

EXCLUDED = {"node_modules", "dist", "release", ".git"}


def sources(folder: Path) -> list[Path]:
    result: list[Path] = []
    for path in sorted(folder.iterdir()):
        if (
            path.name in EXCLUDED
            or path.name.startswith(".env")
            or path.name.endswith(".tsbuildinfo")
        ):
            continue
        if path.is_symlink():
            raise ValueError("Frontend source cannot contain symlinks")
        result.extend(sources(path) if path.is_dir() else [path])
    return result


def verify(root: Path) -> None:
    manifest = json.loads((root / "release/manifest.json").read_text())
    assert manifest["schema"] == 1 and set(manifest["assets"]) == {"admin", "teacher"}
    digest = hashlib.sha256()
    for path in sources(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    assert digest.hexdigest() == manifest["source_sha256"], "Stale frontend release"
    for app in ("admin", "teacher"):
        folder = root / "release" / app
        actual = {}
        for path in sorted(folder.rglob("*")):
            assert not path.is_symlink(), "Asset symlinks are prohibited"
            if path.is_file():
                actual[path.relative_to(folder).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        assert "index.html" in actual and actual == manifest["assets"][app], (
            "Modified asset set"
        )
    print("Frontend source and asset checksums verified")


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
