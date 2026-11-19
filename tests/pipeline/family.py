# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The Google Cloud family's pipeline harness: a stubbed run over a private
copy of the family's own fixture (``tests/fixture``), through the published
test kit (``cs_image_system.system.testing``), with the family's own stubs
(``cs_image_system.gcloud_runtime.testing``) and the Terraform roots
library's standing in for the outside world.

It keeps the names the tests used in cs-image-system-3's shared harness,
from which they moved (spec 005), so each test reads as it did there:
``FixtureRun``, ``copy_config``, ``stub_environment``, ``load_context`` and
the rest. Nothing here names another provider family.
"""
from __future__ import annotations

import functools
import os
import re
import shutil
from pathlib import Path

from cs_image_system.gcloud_runtime import testing as gcloud_testing
from cs_image_system.system import testing as kit
from cs_image_system.system.testing import (
    FIXED_CHECKED_AT,
    FIXED_NOW,
    FIXED_RUN_ID,
    FIXED_TIMESTAMP,
    cli_context,
    command_lines,
    drive_lifecycles,
    load_context,
    module_path,
    modules_beside,
    modules_inside,
    os_type_for_family,
    passing_session,
    plain,
    tree,
)
from cs_image_system.tofu_roots import testing as roots_testing

__all__ = [
    "FIXED_CHECKED_AT",
    "FIXED_NOW",
    "FIXED_RUN_ID",
    "FIXED_TIMESTAMP",
    "FIXTURE_CONFIG",
    "REPO",
    "FixtureRun",
    "cli_context",
    "command_lines",
    "copy_config",
    "drive_lifecycles",
    "load_context",
    "module_path",
    "modules_beside",
    "modules_inside",
    "os_type_for_family",
    "passing_session",
    "plain",
    "private_plugin_cache",
    "record_network_facts",
    "stub_environment",
    "tree",
]

REPO = Path(__file__).resolve().parents[2]
FIXTURE_CONFIG = REPO / "tests" / "fixture"     # the family's own; no run ever applies it


def record_network_facts(root: Path, checked_at: str = FIXED_CHECKED_AT) -> Path:
    """The network facts a real run would have recorded for the tree under
    ``root`` (its ``gcloud`` runtimes' declared networks and subnets)."""
    return gcloud_testing.record_runtime_facts(root, checked_at)


def copy_config(tmp_path: Path, name: str = "config") -> Path:
    """A private copy of the family's fixture, its apply flags off and its
    runtimes non-ephemeral (the kit's copy), with the network facts record
    an offline load adopts."""
    dst = kit.copy_fixture(FIXTURE_CONFIG, tmp_path, name)
    record_network_facts(dst)
    return dst


def stub_environment(monkeypatch, config: Path | None = None) -> list[str]:
    """The core's stubs (tools journaled, never run; the clock and ``USER``
    pinned), the family's (Google Cloud answered from ``config``, the
    fixture by default) and the Terraform roots library's; the command
    journal is returned, and the relabels the stubs made are on
    ``stub_environment.retags``."""
    retags: list[tuple[str, dict[str, str]]] = []
    journal = kit.stub_core(monkeypatch, FIXTURE_CONFIG / kit.IDENTITY_FILE, stubs=(
        functools.partial(gcloud_testing.stub, retags=retags, config=config or FIXTURE_CONFIG),
        roots_testing.stub,
    ))
    stub_environment.retags = retags  # type: ignore[attr-defined]
    return journal


class FixtureRun:
    """One prepared copy of the family's fixture and its loaded context;
    ``run()`` drives lifecycles."""

    def __init__(self, tmp_path: Path, monkeypatch, dry_run: bool = True, config_root: Path | None = None,
                 overlays: list[Path] | None = None, undeclare: list[str] | None = None):
        self.config_root = config_root or copy_config(tmp_path)
        self.journal = stub_environment(monkeypatch, self.config_root)
        self.retags: list[tuple[str, dict[str, str]]] = getattr(stub_environment, "retags", [])
        self._cwd = os.getcwd()
        self.ctx = load_context(self.config_root, dry_run=dry_run, overlays=overlays, undeclare=undeclare)
        self.generated = self.config_root / "generated"
        self.meta_state = self.config_root / "meta-state"

    def run(self, lifecycles: list[str] | str = "all", *, apply: bool = True, commit: bool = False,
            state_query: bool = False, only: list[str] | None = None,
            force_bake: list[str] | None = None):
        return drive_lifecycles(self.ctx, lifecycles, apply=apply, commit=commit, state_query=state_query,
                                only=only, force_bake=force_bake)

    def restore_cwd(self) -> None:
        os.chdir(self._cwd)


def private_plugin_cache(tmp_path: Path, roots: list[Path]) -> Path:
    """A private OpenTofu provider cache under ``tmp_path`` for a test that
    runs the real ``tofu`` (``TF_PLUGIN_CACHE_DIR`` is not safe under
    concurrent ``init``), seeded by COPYING the providers the roots require
    from the shared cache when one is there."""
    private = tmp_path / "plugin-cache"
    private.mkdir(exist_ok=True)
    shared = os.environ.get("TF_PLUGIN_CACHE_DIR")
    if not shared or not Path(shared).is_dir():
        return private
    sources: set[str] = set()
    for r in roots:
        for tf in r.rglob("*.tf"):
            for src in re.findall(r'source\s*=\s*"([^"]+)"', tf.read_text()):
                if src.startswith((".", "/")) or ":" in src:      # a module path or URL
                    continue
                parts = src.split("/")
                if len(parts) == 2:
                    parts = ["registry.opentofu.org", *parts]
                if len(parts) == 3:
                    sources.add("/".join(parts))
    for src in sorted(sources):
        have = Path(shared) / src
        if have.is_dir() and not (private / src).exists():
            shutil.copytree(have, private / src)
    return private
