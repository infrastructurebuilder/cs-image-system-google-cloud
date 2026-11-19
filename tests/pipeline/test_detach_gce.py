# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Detach with a required unmount on Google Cloud: removing a storage from
a launched GCE instance's declaration is planned as a detach after an
unmount. The runtime unmounts it ON the instance first, over the IAP
tunnel with the runtime's declared ``gcloud``, and writes a receipt (a
failed unmount raises and leaves a failed receipt); ``gate-plan
--require-unmounted`` demands that receipt; on GCE a detach is an in-place
attribute, so the gate whitelists no destroy; the launch record drops the
mount only after the apply.

Carried from cs-image-system-3's ``tests/test_detach.py`` as of f3c7472e
(spec 005, T072). The file's other cases (the refusal of any other
launch-parameter change, the receipt gate, the operator's confirmation,
the dry run keeping the record) prove the core's detach and stay there on
the AWS runtime, as does the AWS attachment's whitelisted destroy.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from family import FixtureRun, command_lines

from cs_image_system.base.launch_params import compute_launch_params, record_detachments
from cs_image_system.contract.lifecycles import Lifecycle
from cs_image_system.engine.commands.unmount import read_receipt, unmount_script, unmount_storage

GCE_ROOT = "tofu-gce/instance-generation"


def _launched_with_params(root: Path, name: str, build: str, params: dict) -> None:
    ms = root / "meta-state"
    ms.mkdir(exist_ok=True)
    p = ms / "launch-params.yaml"
    data = yaml.safe_load(p.read_text()) if p.exists() else {}
    data.setdefault("instances", {})[name] = {**params, "build": build, "launched": True, "launched_run": "r0"}
    p.write_text(yaml.safe_dump(data, sort_keys=True))
    pins = ms / "pins.yaml"
    d = yaml.safe_load(pins.read_text()) if pins.exists() else {"images": {}, "instances": {}, "upgrades": []}
    d.setdefault("instances", {})[name] = build
    pins.write_text(yaml.safe_dump(d, sort_keys=True))


def _drop_mount(root: Path, instance: str, storage: str) -> None:
    p = root / "instances" / "instances.yaml"
    d = yaml.safe_load(p.read_text())
    for i in d["instances"]:
        if i["name"] == instance:
            i["storages"] = [s for s in (i.get("storages") or []) if s.get("name") != storage]
    p.write_text(yaml.safe_dump(d, sort_keys=False))


def _lines_in(script: str, workspace: str) -> list[str]:
    return [ln for ln in command_lines(script) if ln.split('"')[1] == workspace]


def _record_current_mounts(run: FixtureRun, root: Path, name: str, build: str) -> list[dict]:
    """Seed the launch record from what the tree computes NOW (so only the
    later declaration change differs)."""
    inst = next(i for i in run.ctx.instances if i.get_name() == name)
    params = compute_launch_params(run.ctx, inst)
    _launched_with_params(root, name, build, params)
    return params["mounts"]


def test_dropping_a_gce_mount_is_planned_as_a_detach_after_an_unmount(family_root, family_run):
    root = family_root
    probe = family_run(config_root=root)
    mounts = _record_current_mounts(probe, root, "gce-test", "dask-gce-1")
    assert [m["storage"] for m in mounts] == ["gce_data"]
    _drop_mount(root, "gce-test", "gce_data")
    run = family_run(config_root=root)
    run.ctx.config["apply_instances"] = ["gcloud-east1"]
    summary = run.run(["instance-image"], apply=True, only=["none"])
    assert summary.ok, summary.validation_errors or summary.error      # a mount removal is allowed
    lines = _lines_in((run.generated / "instance-image" / "run-instance-image.sh").read_text(), GCE_ROOT)
    unmount = next(i for i, ln in enumerate(lines) if "unmount storage --instance gce-test --storage gce_data" in ln)
    plan = next(i for i, ln in enumerate(lines) if "plan -input=false" in ln)
    gate = next(ln for ln in lines if "gate-plan" in ln)
    assert unmount < plan
    assert "--mount-point /mnt/gce-data" in lines[unmount] and "--root-dir" in lines[unmount]
    assert "--require-unmounted gce-test:gce_data" in gate
    assert "--allow-destroy" not in gate                                  # GCE: an in-place attribute
    # the record keeps the mount until the detach applied
    assert [m["storage"] for m in run.ctx.meta_state.launch_params()["gce-test"]["mounts"]] == ["gce_data"]
    # after the apply the record drops it
    record_detachments(run.ctx, Lifecycle.INSTANCE_IMAGE)
    rec = run.ctx.meta_state.launch_params()["gce-test"]
    assert rec["mounts"] == [] and rec["launched"] is True and rec["launched_run"] == "r0"


def test_gce_unmount_runs_over_the_iap_tunnel_and_writes_the_receipt(family_root, family_run, monkeypatch):
    root = family_root
    run = family_run(config_root=root)
    calls: list[list[str]] = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout="unmounted: /mnt/gce-data\n", stderr="")
    monkeypatch.setattr(subprocess, "run", fake_run)
    result = unmount_storage(run.ctx, "gce-test", "gce_data", "/mnt/gce-data", root / "ws")
    assert result["ok"] and result["method"] == "session"
    cmd = calls[-1]
    # the runtime's declared gcloud, not a bare name from PATH
    assert cmd[:4] == ["/usr/local/bin/gcloud", "compute", "ssh", "gce-test"] and "--tunnel-through-iap" in cmd
    assert "--project" in cmd and "csis-sandbox" in cmd and "us-east1-b" in cmd
    script = cmd[cmd.index("--command") + 1]
    assert script == unmount_script("/mnt/gce-data")
    assert 'umount "$MP"' in script and "/etc/fstab" in script and "still mounted" in script
    receipt = read_receipt(root / "ws", "gce-test", "gce_data")
    assert receipt is not None
    assert receipt["ok"] and receipt["runtime"] == "gcloud-east1" and receipt["exit_status"] == 0
    # a failed unmount raises and leaves a failed receipt
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: SimpleNamespace(returncode=1, stdout="", stderr="busy"))
    with pytest.raises(RuntimeError, match="failed"):
        unmount_storage(run.ctx, "gce-test", "gce_data", "/mnt/gce-data", root / "ws")
    failed = read_receipt(root / "ws", "gce-test", "gce_data")
    assert failed is not None and failed["ok"] is False
