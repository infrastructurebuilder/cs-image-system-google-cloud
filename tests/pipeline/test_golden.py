# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Pins the Google Cloud family's emission for its own fixture.

A failure here means what the runtime, its roots or its state backend
generate has changed. If the change is intended, run ``just golden-regen``
and read the rewritten files one by one.
"""
from __future__ import annotations

from cs_image_system.system import testing as kit


def test_the_emission_matches_the_family_golden(family_run, golden_dir):
    run = family_run()
    summary = run.run("all", apply=True)
    assert summary.ok, summary.error
    kit.assert_matches(golden_dir, kit.emitted(run.generated, run.meta_state),
                       regenerate_with="just golden-regen")


def test_the_fixture_declares_google_cloud_and_nothing_of_another_provider(family_run):
    """The family's fixture is a Google Cloud tree: one runtime, the
    family's, and every instance, storage and state builder the family's
    own."""
    ctx = family_run().ctx
    families = {"gcloud_runtime", "tf_gcp_plugin", "gcs_state_plugin"}
    assert [type(rb).__module__.split(".")[1] for rb in ctx.runtime_builders.values()] == ["gcloud_runtime"]
    for builders in (ctx.instance_builders, ctx.storage_builders):
        assert {type(b).__module__.split(".")[1] for b in builders.values()} <= families
