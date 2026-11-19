# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The state query asks Google Cloud which image a launched GCE instance
booted (finding 49): an image differing from the instance's pin is changed
drift, a matching one is clean, and an unanswered query is reported
unavailable, never dropped. The GCE runtime implements the query; with its
capability stubbed back off the query makes no claim.

Carried from cs-image-system-3's ``tests/test_state_query.py`` (spec 005,
T024). The drift classes, the import and the validator are the core's and
stay there, proven on AWS. The ``world`` fixture keeps the source's shape
less its AWS and Okta stubs: Google Cloud's image listing is the family
stub's (nothing of ours exists), every storage builder answers "absent"
(no ``gcloud`` is run), and the family's group is POSIX, whose builder has
no provider to ask.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from family import FixtureRun

from cs_image_system.engine import state_query as sq
from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder


def _build(build_id: str, series: str, runtime: str, run: str = "run-1", parent: str = "external",
           fp: str = "abcdef0123456789") -> dict:
    return {"build_id": build_id, "series": series, "runtime": runtime, "name": f"{series}-{build_id}",
            "parent": parent, "input_fingerprint": fp, "run": run,
            "capabilities": {"identity_types": ["posix"], "storage_types": ["pd"]}, "mods": [], "chain": []}


@pytest.fixture
def world(tmp_path: Path, monkeypatch):
    """A context whose storage builders answer from canned reality."""
    from cs_image_system.tofu_roots.tofu_storage_builder import TofuStorageBuilderBase

    reality: dict = {"storages": {}}
    run = FixtureRun(tmp_path, monkeypatch)   # first: its stubs would override ours
    monkeypatch.setattr(TofuStorageBuilderBase, "query_state",
                        lambda self: {s.get_name(): reality["storages"].get(s.get_name(), {"present": False, "type": self.capability_type()})
                                      for s in self.model._storages})
    try:
        yield run, reality
    finally:
        run.restore_cwd()


def _gce_runtime(ctx) -> str:
    return sorted(n for n, b in ctx.runtime_builders.items() if isinstance(b, GCPCloudBuilder))[0]


def test_booted_image_differing_from_the_pin_is_changed_drift(world, monkeypatch):
    """Finding 49: a pin moved to a new series head while the instance kept
    running the old image, and nothing compared the two."""
    run, _ = world
    ctx = run.ctx
    rt = _gce_runtime(ctx)
    ctx.meta_state.add_build(_build("img-old", "imgfile-basic-dask", rt))
    ctx.meta_state.add_build(_build("img-new", "imgfile-basic-dask", rt))
    ctx.meta_state.bind_instance("gce-test", "img-new", "run-x")
    ctx.meta_state.record_launch_params("gce-test", {"launched": True})   # a machine never launched is not asked
    monkeypatch.setattr(GCPCloudBuilder, "query_instance_boot_image", lambda self, name: "img-old")
    report = sq.query_state(ctx)
    hits = [d for d in report.drift if d.kind == "instance" and d.name == "gce-test"]
    assert len(hits) == 1 and hits[0].drift == sq.DRIFT_CHANGED
    assert "booted image img-old" in hits[0].detail and "img-new" in hits[0].detail


def test_booted_image_matching_the_pin_is_clean_and_unanswered_is_unavailable(world, monkeypatch):
    run, _ = world
    ctx = run.ctx
    rt = _gce_runtime(ctx)
    ctx.meta_state.add_build(_build("img-new", "imgfile-basic-dask", rt))
    ctx.meta_state.bind_instance("gce-test", "img-new", "run-x")
    ctx.meta_state.record_launch_params("gce-test", {"launched": True})   # a machine never launched is not asked
    monkeypatch.setattr(GCPCloudBuilder, "query_instance_boot_image", lambda self, name: "img-new")
    report = sq.query_state(ctx)
    assert not [d for d in report.drift if d.kind == "instance"]
    monkeypatch.setattr(GCPCloudBuilder, "query_instance_boot_image", lambda self, name: None)
    report = sq.query_state(ctx)
    assert not [d for d in report.drift if d.kind == "instance"]
    assert any("instances/gce-test" in u for u in report.unavailable)


def test_runtimes_without_the_boot_query_make_no_claim(world, monkeypatch):
    """In cs-image-system-3 this case stubs the AWS runtime's capability off;
    here it is the GCE runtime's: the runtime says it can answer, and with
    that stubbed back off a pinned, launched instance is neither drift nor
    unavailable (the launch is recorded here so that the capability, not the
    never-launched rule, is what keeps the query from asking)."""
    run, _ = world
    ctx = run.ctx
    rtb = ctx.runtime_builders[_gce_runtime(ctx)]
    assert rtb.can_query_instance_boot_image() is True             # Google Cloud implements the boot query
    monkeypatch.setattr(GCPCloudBuilder, "can_query_instance_boot_image", lambda self: False)
    monkeypatch.setattr(GCPCloudBuilder, "query_instance_boot_image",
                        lambda self, name: pytest.fail("asked a runtime that says it cannot answer"))
    ctx.meta_state.add_build(_build("img-new", "imgfile-basic-dask", rtb.get_name()))
    ctx.meta_state.bind_instance("gce-test", "img-new", "run-x")
    ctx.meta_state.record_launch_params("gce-test", {"launched": True})
    report = sq.query_state(ctx)
    assert not [d for d in report.drift if d.kind == "instance"]
    assert not [u for u in report.unavailable if "instances/" in u]
