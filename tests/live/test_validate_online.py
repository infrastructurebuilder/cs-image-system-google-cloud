# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The family's live proof, read-only: the fixture validated against Google
Cloud itself.

``validate --online`` asks the runtime's project for its networks and
subnets (no resource is created, nothing is billed) and records what it
found in the copy's ``meta-state/runtime-facts.yaml``. It needs a Google
Cloud session with read access to the fixture's project (application
default credentials, or the CI job's federated identity), and fails,
never skips, without one. Run by ``just test-live``, never by ``just test``.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import yaml

FIXTURE = Path(__file__).resolve().parents[1] / "fixture"


def test_the_fixture_validates_against_google_cloud(tmp_path: Path):
    root = tmp_path / "config"
    shutil.copytree(FIXTURE, root, ignore=shutil.ignore_patterns("meta-state", "generated"))
    cli = shutil.which("cs-image-system")
    assert cli, "the command line is not installed in this environment (just init)"
    env = {**os.environ, "CSIS_CONFIG_IDENTITY": str(FIXTURE / ".age-identity")}
    done = subprocess.run([cli, "--root-dir", str(root), "validate", "--online"], env=env,
                          capture_output=True, text=True, timeout=600)
    assert done.returncode == 0, done.stdout[-4000:] + done.stderr[-4000:]
    facts = yaml.safe_load((root / "meta-state" / "runtime-facts.yaml").read_text())
    assert "gcloud-east1" in facts["runtimes"], facts
