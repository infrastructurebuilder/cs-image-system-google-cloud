# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The system's starters as whole trees, for the tests that read one.

The starters ship inside the installed system (``cs_image_system.system``);
a tree is a skeleton plus an overlay, and its Terraform modules are the
installed plugins'. ``RENDERED()`` writes every starter once per process
and hands back the directory that holds them, ``<dir>/<name>/``. The
helpers keep the names the tests used in cs-image-system-3, from which they
moved (spec 005).
"""
from __future__ import annotations

import atexit
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from cs_image_system.system import starters

#: the installed system's starter sources (the skeleton and each overlay)
EXAMPLES = starters.starters_root()

_rendered: Path | None = None


def RENDERED() -> Path:  # noqa: N802 - a constant's name, computed once
    """Every starter of the installed release written once per process,
    one directory each, removed when the process ends."""
    global _rendered
    if _rendered is None:
        into = Path(tempfile.mkdtemp(prefix="csis-starters-"))
        version = starters.release_version()
        for name in starters.STARTERS:
            starters.write_starter(name, into / name, version=version)
        atexit.register(shutil.rmtree, into, True)
        _rendered = into
    return _rendered


def _assigned(text: str, key: str, value: str) -> bool:
    """``key = value`` on a line of HCL, however aligned."""
    return re.search(rf"^\s*{re.escape(key)}\s*=\s*{re.escape(value)}\s*$", text, flags=re.M) is not None


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def _starter_copy(tmp_path: Path, name: str = "standard-gce", remote: str | None = "git@github.com:acme/widgets.git") -> Path:
    """A rendered starter copied under ``tmp_path/tree`` as a git checkout
    on ``develop``, with ``remote`` as its origin."""
    root = tmp_path / "tree"
    shutil.copytree(RENDERED() / name, root)
    _git(root, "init", "-q", "-b", "develop")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    if remote:
        _git(root, "remote", "add", "origin", remote)
    return root
