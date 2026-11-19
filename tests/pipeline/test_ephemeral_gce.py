# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""An ephemeral GCE instance is verified through Google Cloud's own hook:
the runtime reads the instance's serial console until the guest agent says
the startup scripts finished, fails fast on an explicit failure line,
compares the booted image with the expected build, and reads each declared
mount point's own line; the verdict is recorded.

Carried from cs-image-system-3's ``tests/test_ephemeral.py`` (spec 005,
T024). The file's other cases prove the core's ephemeral sequence and
failure policy through GCE; they are re-hosted there on the AWS runtime
(T039), so only the serial-console case, which is Google Cloud's alone,
comes here.
"""
from __future__ import annotations

import pytest

from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder

CONSOLE_OK = """
Sep  8 14:07:27 gce-test systemd[1]: Starting google-startup-scripts.service...
[   47.164059] XFS (sdb): Ending clean mount
Sep  8 14:07:35 gce-test google_metadata_script_runner[1229]: startup-script: csis-mount: /mnt/gce-data mounted
Sep  8 14:07:35 gce-test google_metadata_script_runner[1229]: Finished running startup scripts
"""
CONSOLE_FAIL = "Sep  8 14:07:35 gce-test google_metadata_script_runner[1229]: startup-script exit status 1\n"


def test_gce_verification_reads_the_serial_console_and_records_the_verdict(prepared, monkeypatch):
    from cs_image_system.base.commands.verify_instance import VerificationFailed, verify_instance
    root, make = prepared
    run = make()
    assert run.run(["instance-image"], apply=False, only=["none"]).ok
    monkeypatch.setattr(GCPCloudBuilder, "serial_console", lambda self, name: CONSOLE_OK)
    monkeypatch.setattr(GCPCloudBuilder, "query_instance_boot_image", lambda self, name: "dask-build-1")
    monkeypatch.setattr("time.sleep", lambda s: None)
    record = verify_instance(run.ctx, "gce-test", expected_build="dask-build-1", timeout=1)
    assert record["ok"] and record["ephemeral"] is True
    names = {c["name"]: c["ok"] for c in record["checks"]}
    assert names == {"startup scripts": True, "booted image": True, "data disks mounted": True,
                     "declared tests": True}          # the dask image declares post-bake tests
    assert run.ctx.meta_state.verifications()[-1]["instance"] == "gce-test"
    # an explicit failure line fails fast, and the record says which check
    monkeypatch.setattr(GCPCloudBuilder, "serial_console", lambda self, name: CONSOLE_FAIL)
    with pytest.raises(VerificationFailed, match="startup scripts: an explicit failure line"):
        verify_instance(run.ctx, "gce-test", expected_build="dask-build-1", timeout=1)
    assert run.ctx.meta_state.verifications()[-1]["ok"] is False
    # a wrong booted image fails too
    monkeypatch.setattr(GCPCloudBuilder, "serial_console", lambda self, name: CONSOLE_OK)
    with pytest.raises(VerificationFailed, match="booted image"):
        verify_instance(run.ctx, "gce-test", expected_build="dask-build-2", timeout=1)
    # no completion within the timeout
    monkeypatch.setattr(GCPCloudBuilder, "serial_console", lambda self, name: "booting...\n")
    with pytest.raises(VerificationFailed, match="no completion"):
        verify_instance(run.ctx, "gce-test", expected_build="dask-build-1", timeout=0)
