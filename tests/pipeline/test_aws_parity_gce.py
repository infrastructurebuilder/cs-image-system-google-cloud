# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""``lineage relabel`` on Google Cloud: a follow image baked in the same run
as its parent keeps packer's generation-time labels (a ``series-...``
parent, a placeholder fingerprint); its lineage record is the truth, so
relabel re-labels that image alone, with the owning configuration's id,
and a dry run plans the same and labels nothing.

Carried from cs-image-system-3's ``tests/test_aws_parity.py`` (spec 005,
T024): its two relabel cases, which ran on the shared fixture's GCE runtime
and stub Google Cloud's image listing. The rest of that file is AWS parity
(the booted-image query, AMI disposal, SSM verification, ephemeral AWS
instances, restamp, the SSM invocation race) and stays there. The lineage
records' identity capability is the family's (``posix``); the relabel
compares parent and fingerprint, not capabilities.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from family import FixtureRun, copy_config

from cs_image_system.engine.commands.relabel import relabel, relabel_plan
from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder


def _seed_follow_pair(ms) -> None:
    common = {"parent": "vendor", "chain": [], "mods": [], "local_mods": False, "update": None,
              "tests": {"assertions": 0, "in_bake": True},
              "capabilities": {"identity_types": ["posix"], "storage_types": ["pd"]},
              "run": "2026_09_08t12_48_23_888542", "runtime": "gcloud-east1"}
    ms.add_build({**common, "build_id": "base-1", "series": "basic-rh-10", "name": "b",
                  "input_fingerprint": "e792c328f39cd099" + "0" * 48})
    ms.add_build({**common, "build_id": "dask-1", "series": "imgfile-basic-dask", "name": "d",
                  "parent": "base-1", "input_fingerprint": "1733b718d8c52101" + "0" * 48})


def _real_images(dask_parent="series-basic-rh-10", dask_fp="293d6de5ab5f3b4f"):
    return [
        {"image_id": "base-1", "name": "base-1", "state": "READY", "created": "", "tags": {
            "csis_series": "basic-rh-10", "csis_parent": "vendor", "csis_run": "2026_09_08t12_48_23_888542",
            "csis_fingerprint": "e792c328f39cd099", "csis_config": "cs-image-action-test"}},
        {"image_id": "dask-1", "name": "dask-1", "state": "READY", "created": "", "tags": {
            "csis_series": "imgfile-basic-dask", "csis_parent": dask_parent, "csis_run": "2026_09_08t12_48_23_888542",
            "csis_fingerprint": dask_fp, "csis_config": "cs-image-action-test"}},
    ]


def test_relabel_retags_only_the_images_whose_tags_disagree_with_their_record(tmp_path: Path, monkeypatch):
    """The live case: a follow image baked in the same run as its
    parent kept packer's generation-time labels (`series-...` parent, a
    placeholder fingerprint); its record is the truth, so relabel re-tags it
    and leaves the consistent base image alone."""
    root = copy_config(tmp_path)
    run = FixtureRun(tmp_path, monkeypatch, config_root=root, dry_run=False)
    retags = run.retags
    try:
        _seed_follow_pair(run.ctx.meta_state)
        monkeypatch.setattr(GCPCloudBuilder, "query_images", lambda self, series: _real_images())
        plan = relabel_plan(run.ctx, "gcloud-east1")
        assert [(r.build_id, r.differences) for r in plan] == [
            ("dask-1", ["parent: tag=series-basic-rh-10 record=base-1",
                        "fingerprint: tag=293d6de5ab5f3b4f record=1733b718d8c52101"])]
        results = relabel(run.ctx, "gcloud-east1")
        assert results[0].retagged is True
        assert retags[-1] == ("dask-1", {"csis_series": "imgfile-basic-dask", "csis_parent": "base-1",
                                         "csis_run": "2026_09_08t12_48_23_888542",
                                         "csis_fingerprint": "1733b718d8c52101",
                                         "csis_config": "cs-image-action-test"})    # the owning configuration
        monkeypatch.setattr(GCPCloudBuilder, "query_images",
                            lambda self, series: _real_images("base-1", "1733b718d8c52101"))
        assert relabel_plan(run.ctx, "gcloud-east1") == []                 # reality now matches
        with pytest.raises(ValueError, match="unknown runtime"):
            relabel_plan(run.ctx, "nowhere")
    finally:
        run.restore_cwd()


def test_relabel_dry_run_retags_nothing(tmp_path: Path, monkeypatch):
    root = copy_config(tmp_path)
    run = FixtureRun(tmp_path, monkeypatch, config_root=root)                    # dry run
    try:
        _seed_follow_pair(run.ctx.meta_state)
        monkeypatch.setattr(GCPCloudBuilder, "query_images", lambda self, series: _real_images())
        plan = relabel(run.ctx, "gcloud-east1", builds=["dask-1"])
        assert [r.build_id for r in plan] == ["dask-1"] and plan[0].retagged is None
        assert run.retags == []
    finally:
        run.restore_cwd()
