# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The Google Cloud family's pipeline tests: what needs a whole run.

Each drives a stubbed run over a private copy of the family's own fixture
(``tests/fixture``) through the published test kit, with the family's stubs
standing in for Google Cloud (``family.py``), and the golden test compares
what the run emits with the family's own golden (``tests/golden``).
"""
from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml
from family import FIXTURE_CONFIG, FixtureRun, copy_config

from cs_image_system.system.testing import isolation

# every pipeline test finds the root logger as the session started it
root_logger_restored = pytest.fixture(autouse=True)(isolation.root_logger_restored)

TESTS = Path(__file__).resolve().parents[1]
GOLDEN = TESTS / "golden"


@pytest.fixture(autouse=True)
def _no_ambient_google_credentials(tmp_path_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test reads the developer's own Google Cloud credentials: the
    application-default file is pointed at one that does not exist."""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path_factory.mktemp("gcp-empty") / "no-adc.json"))


@pytest.fixture
def fixture_dir() -> Path:
    """The family's fixture configuration."""
    return FIXTURE_CONFIG


@pytest.fixture
def golden_dir() -> Path:
    """The family's golden: the fixture's pinned emission."""
    return GOLDEN


@pytest.fixture
def family_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., FixtureRun]]:
    """A factory for stubbed runs over a private copy of the family's
    fixture; keyword arguments reach ``FixtureRun``. The working directory
    is restored when the test ends."""
    made: list[FixtureRun] = []

    def make(**kwargs) -> FixtureRun:
        run = FixtureRun(tmp_path, monkeypatch, **kwargs)
        made.append(run)
        return run

    yield make
    for run in made:
        run.restore_cwd()


@pytest.fixture
def family_root(tmp_path: Path) -> Path:
    """A private copy of the family's fixture, for a test to edit before it
    loads it."""
    return copy_config(tmp_path)


def declare_ephemeral(root: Path, name: str) -> None:
    """Mark the instance ``name`` of the tree under ``root`` ephemeral."""
    p = root / "instances" / "instances.yaml"
    d = yaml.safe_load(p.read_text())
    for i in d["instances"]:
        if i["name"] == name:
            i["ephemeral"] = True
    p.write_text(yaml.safe_dump(d, sort_keys=False))


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A private copy of the fixture with ``gce-test`` ephemeral, and a
    factory for stubbed runs over it: ``(root, make)``."""
    root = copy_config(tmp_path)
    declare_ephemeral(root, "gce-test")
    runs: list[FixtureRun] = []

    def make(**kw) -> FixtureRun:
        run = FixtureRun(tmp_path, monkeypatch, config_root=root, **kw)
        runs.append(run)
        return run
    try:
        yield root, make
    finally:
        for r in runs:
            r.restore_cwd()
