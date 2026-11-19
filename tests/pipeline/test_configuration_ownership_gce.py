# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""What the Google Cloud family makes carries its configuration's id, and
its lookups and inventory count this configuration's alone (stage 93, the
walk's F47 and F53).

Every GCE storage and instance module call labels its thing
``csis_config``; a GCE machine of our name whose labels are another
configuration's reads as absent; the emptiness check over the GCE
inventory leaves another configuration's things alone, says so, and names
the unlabelled.

Carried from cs-image-system-3's ``tests/test_configuration_ownership.py``
(spec 005, T024). Its EBS, S3 and EC2 lookups and its relabel of AWS
storages and machines are AWS's and stay there; the module-call case is
carried for the family's roots, which are all this fixture declares.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from family import FixtureRun, copy_config

from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder

OURS = "cs-image-action-test"          # the fixture's top-level id
THEIRS = "cs-image-system-walk"
GCE = "gcloud-east1"


@pytest.fixture
def run(tmp_path: Path, monkeypatch):
    r = FixtureRun(tmp_path, monkeypatch, config_root=copy_config(tmp_path), dry_run=False)
    try:
        yield r
    finally:
        r.restore_cwd()


# ------------------------------------------------------------ 1. everything carries the id

def test_every_storage_and_instance_module_call_carries_the_id(run):
    assert run.run(["storage", "instance-image"], apply=False).ok
    calls = [p for p in run.generated.rglob("*.tf") if "storage-generation" in str(p) or "instance-generation" in str(p)]
    assert calls
    # the family's three roots are among the files read
    assert {p.relative_to(run.generated).parts[1] for p in calls} >= {"gcp-pd", "gcp-gcs", "tofu-gce"}
    missing = []
    for p in calls:
        text = p.read_text()
        if "module \"" in text and ("tags" in text or "labels" in text) and f'"csis_config" = "{OURS}"' not in text:
            missing.append(str(p.relative_to(run.generated)))
    assert not missing, missing


# ------------------------------------------------------------ 2. lookups take ours, never theirs

def test_gce_lookups_and_inventory_tell_ours_from_theirs(run, monkeypatch):
    rtb = run.ctx.runtime_builders[GCE]
    assert isinstance(rtb, GCPCloudBuilder)
    assert rtb._theirs(SimpleNamespace(labels={"csis_config": THEIRS}))
    assert not rtb._theirs(SimpleNamespace(labels={"csis_config": OURS}))
    assert not rtb._theirs(SimpleNamespace(labels={}))

    # a machine of our name whose labels are theirs reads as absent
    class Client:
        def get(self, project, zone, instance):
            return SimpleNamespace(status="RUNNING", labels={"csis_config": THEIRS}, hostname="", id="1")
    monkeypatch.setattr(GCPCloudBuilder, "_instances_client", lambda self: (Client(), "p", "z"))
    assert rtb.query_instance_power_state("gce-test") == "absent"
    assert rtb.query_instance_identity("gce-test") is None
    assert rtb.instance_tags("gce-test") == {"csis_config": THEIRS}


def test_emptiness_leaves_another_configurations_things_alone_and_names_the_unlabelled(run, monkeypatch):
    from cs_image_system.engine.commands.runtime_facts import emptiness
    monkeypatch.setattr(GCPCloudBuilder, "inventory", lambda self: {
        "instances": ["walk-gce-1", "scratch"], "images": ["team-node-x"],
        "disks": ["gce-data", "their-data", "old-scratch"], "buckets": ["csis-sandbox-86233086783-default-bucket", "their-bucket"],
        "owners": {"instances": {"walk-gce-1": THEIRS, "scratch": OURS}, "images": {"team-node-x": THEIRS},
                   "disks": {"their-data": THEIRS, "gce-data": OURS}, "buckets": {"their-bucket": THEIRS}}})
    result = emptiness(run.ctx, GCE)
    assert result["leftovers"] == {"instances": ["scratch"], "images": [], "disks": ["old-scratch"], "buckets": []}
    assert result["elsewhere"] == {"instances": {THEIRS: 1}, "images": {THEIRS: 1}, "disks": {THEIRS: 1}, "buckets": {THEIRS: 1}}
    assert result["unlabelled"] == {"disks": ["old-scratch"]}
    assert not result["empty"]
    # with nothing of ours beyond the declared storages, theirs alone does not make the runtime un-empty
    monkeypatch.setattr(GCPCloudBuilder, "inventory", lambda self: {
        "instances": ["walk-gce-1"], "images": [], "disks": ["gce-data"], "buckets": ["csis-sandbox-86233086783-default-bucket"],
        "owners": {"instances": {"walk-gce-1": THEIRS}}})
    result = emptiness(run.ctx, GCE)
    assert result["empty"] and result["elsewhere"] == {"instances": {THEIRS: 1}}
