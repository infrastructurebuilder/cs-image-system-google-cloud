# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The tunnel a real ssh login proof rides to a GCE machine is Google
Cloud's own: on a runtime whose session mechanism is ``iap``, the runtime's
proxy command is ``gcloud compute start-iap-tunnel`` on stdin, for the
runtime's project and zone.

Carried from cs-image-system-3's ``tests/test_posix_identity.py`` (spec 005,
T024). The rest of that file proves the core's identity seams, the POSIX
plugin and the Okta plugin; the AWS tunnel (SSM) is AWS's and stays there.
"""
from __future__ import annotations

from pathlib import Path

from family import copy_config, load_context, stub_environment


def test_the_gce_tunnel_is_iap_on_stdin(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(Path.cwd())                               # the load moves the working directory; this restores it
    stub_environment(monkeypatch)
    ctx = load_context(copy_config(tmp_path))
    rtb = ctx.runtime_builders["gcloud-east1"]                  # the fixture's GCE runtime: session_mechanism iap
    cmd = rtb.ssh_proxy_command("gce-test") or []
    assert cmd[1:5] == ["compute", "start-iap-tunnel", "gce-test", "%p"] and "--listen-on-stdin" in cmd
    assert cmd[cmd.index("--project") + 1] == "csis-sandbox" and cmd[cmd.index("--zone") + 1] == "us-east1-b"
