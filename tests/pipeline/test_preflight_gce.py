# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The preflight's Google Cloud session line: Application Default
Credentials refresh themselves, so the preflight judges them (present, no
fixed expiry) rather than leaving them NOT JUDGED, and over the family's
fixture it closes green with one line naming the runtime, its state
backend and the ADC's kind.

Carried from cs-image-system-3's ``tests/test_preflight_sessions.py`` as of
f3c7472e (spec 005, T073): the ``gcloud`` line of
``test_static_keys_are_present_and_not_judged`` ("a credential that renews
itself is judged"), here also held through the runtime's own hook and the
command. The file's other cases (static AWS keys present and not judged,
never a green close over them) are the core's on the AWS runtime and stay
there.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from family import FIXTURE_CONFIG, stub_environment
from typer.testing import CliRunner

runner = CliRunner()


def test_a_gcloud_credential_that_renews_itself_is_judged(tmp_path, monkeypatch):
    from cs_image_system.engine.commands import preflight
    from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder
    assert preflight.SessionInfo("r", "gcloud", "ADC", None, "refreshes itself", renews=True).judged
    adc = tmp_path / "adc.json"
    adc.write_text(json.dumps({"type": "authorized_user"}))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(adc))
    status = GCPCloudBuilder.session_status({}, {})
    assert status is not None                      # the runtime answers the hook
    info = preflight._from_status("r", "gcloud", status)
    assert info.present and info.judged
    line = info.line(datetime.now(timezone.utc), expected=30)
    assert "NOT JUDGED" not in line and "refreshes itself" in line, line


def test_the_preflight_closes_green_on_the_google_cloud_line(tmp_path, monkeypatch):
    from cs_image_system.system.cli import app
    monkeypatch.chdir(tmp_path)                    # `preflight` loads the tree, which moves the working directory
    stub_environment(monkeypatch)                  # `preflight` loads the tree (no cloud); the stubs open it
    adc = tmp_path / "adc.json"
    adc.write_text(json.dumps({"type": "authorized_user"}))
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(adc))
    result = runner.invoke(app, ["--root-dir", str(FIXTURE_CONFIG), "preflight"])
    assert result.exit_code == 0, result.output                       # present: exit 0, by the contract (no cloud call)
    line = next(ln for ln in result.output.splitlines() if ln.startswith("session: gcloud-east1"))
    assert "gcloud" in line and "ADC authorized_user" in line and "refreshes itself" in line, line
    assert "NOT JUDGED" not in result.output and "every session present" in result.output, result.output
