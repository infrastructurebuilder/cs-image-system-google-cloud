# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The OS type owns the package manager, on Google Cloud too: for an
alpine image (a family the fixture declares no base image for) the IAP
runtime's session agent installs ``google-guest-agent`` with apk, and the
filestore storage's prerequisites install ``nfs-utils`` with apk; none of
their lines says what the rpm or deb families would.

Carried from cs-image-system-3's ``tests/test_os_types.py`` as of f3c7472e
(spec 005, T073): ``test_the_filestore_storage_bakes_apk_on_alpine`` and
the IAP runtime's half of ``test_an_alpine_image_bakes_through_the_hooks``.
The file's other cases (the resolver, the three types, the posix, AWS and
Okta plugins' lines) prove the core and the other plugins, and stay there.
"""
from __future__ import annotations

import re
from types import SimpleNamespace
from typing import Any, cast

from family import os_type_for_family

OTHER_MANAGERS = re.compile(r"(?<![a-z0-9])(yum|dnf|apt-get|apt|dpkg|rpm)(?![a-z0-9])")


def _says_only_apk(lines: list[str]) -> None:
    commands = [line for line in lines if not line.startswith("#")]
    wrong = [line for line in commands if OTHER_MANAGERS.search(line)]
    assert wrong == [], f"an alpine bake would run another family's package manager: {wrong}"


def test_the_iap_runtimes_session_agent_bakes_apk_on_alpine(family_run):
    ctx = family_run().ctx
    gcp = next(r for r in ctx.runtime_builders.values() if r.session_mechanism() == "iap")
    gcp_lines = gcp.session_agent_commands("alpine")
    assert any("sudo apk add --no-cache google-guest-agent" in line for line in gcp_lines)
    _says_only_apk(gcp_lines)


def test_the_filestore_storage_bakes_apk_on_alpine():
    from cs_image_system.tf_gcp_plugin.tf_gcp_storage_builder import TofuFilestoreStorageBuilder
    # the builder asks the images service for the OS type: the stub's
    # context carries that one service, answered by the kit's own lookup
    images = SimpleNamespace(os_type_for_family=os_type_for_family)
    ctx = SimpleNamespace(services=SimpleNamespace(images=images))
    stub = cast(Any, SimpleNamespace(get_name=lambda: "fs", _get_context=lambda: ctx))
    lines = TofuFilestoreStorageBuilder.base_image_prerequisites(stub, "alpine")
    assert lines[1] == "sudo apk add --no-cache nfs-utils"
    _says_only_apk(lines)
