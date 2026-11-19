# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The version check of the ``gcloud`` executable is the runtime plugin's
own: an executable named ``gcloud`` finds ``GCPCLIVersionChecker`` by its
name, which reads the SDK's version (``Google Cloud SDK 585.0.0``, not the
``core`` component's date-shaped one) and judges the declared requirement.

Carried from cs-image-system-3's ``tests/test_version_checks.py`` (spec 005,
T024): the ``gcloud`` row of its lookup case and its ``gcloud``
parametrization of the version case. The other tools' checkers (packer,
tofu, aws-cli, docker, ansible, bash, the generic default) are the core's
or other families' and stay there.
"""
from __future__ import annotations

from pathlib import Path

import pytest

NAME, TYPE = "gcloud", "executable"
OUTPUT = "Google Cloud SDK 585.0.0\nbq 2.1.29\ncore 2026.09.11\ngsutil 5.35"
REQUIREMENT, VERSION = ">=500", "585.0.0"


@pytest.fixture
def plugins():
    """The installed plugins in a registry of the test's own: where a
    checker is looked up, as a run looks it up in ``ctx.reg``."""
    from cs_image_system.engine.loader import installed_registry
    return installed_registry()


def _fake(tmp_path: Path, name: str, output: str) -> str:
    script = tmp_path / f"fake-{name}"
    body = "\n".join(output.splitlines())
    script.write_text("#!/bin/sh\ncat <<'CSIS_EOF'\n" + body + "\nCSIS_EOF\n")
    script.chmod(0o755)
    return str(script)


def test_gcloud_finds_its_checker_by_name(plugins):
    from cs_image_system.base.models.executable import ExecutableModel
    from cs_image_system.engine.commands.validate import version_checker_for
    from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCLIVersionChecker
    found = version_checker_for(ExecutableModel(name=NAME, type_=TYPE), plugins)
    assert found is GCPCLIVersionChecker and found.__name__ == "GCPCLIVersionChecker"


def test_the_gcloud_checker_reads_the_sdk_version_and_judges_the_requirement(plugins, tmp_path):
    from cs_image_system.base.models.executable import ExecutableModel
    from cs_image_system.engine.commands.validate import check_single_version
    binary = _fake(tmp_path, NAME, OUTPUT)
    checked: list[str] = []
    assert check_single_version(ExecutableModel(name=NAME, type_=TYPE, binary=binary, version=REQUIREMENT), plugins,
                                checked=checked) == []
    assert checked == [f"{NAME} {VERSION} ok ({REQUIREMENT})"]
    (error,) = check_single_version(ExecutableModel(name=NAME, type_=TYPE, binary=binary, version=f">{VERSION}"), plugins)
    assert f"{NAME} {VERSION}" in str(error) and f">{VERSION}" in str(error)
