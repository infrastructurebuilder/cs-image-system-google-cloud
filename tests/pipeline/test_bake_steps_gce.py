# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""A GCE bake does not wait for Systems Manager: the settle the system
emits at the head of every bake waits for the AWS account's Systems
Manager on the AWS runtime only, so no googlecompute build names it or its
document worker.

Carried from cs-image-system-3's ``tests/test_bake_steps.py`` as of
f3c7472e (spec 005, T073): the GCE half of
``test_the_aws_bakes_wait_for_systems_manager_and_the_gce_ones_do_not``
(the AWS half stays there). The file's other cases (the step runner, the
settle, the starters' base tests) are the core's and stay there.
"""
from __future__ import annotations


def test_the_gce_bakes_do_not_wait_for_systems_manager(family_run):
    run = family_run()
    assert run.run(["base-image", "instance-image"], apply=False).ok
    builds = {str(p.relative_to(run.generated)): p.read_text() for p in run.generated.rglob("*-build.pkr.hcl")}
    gce = "".join(t for p, t in builds.items() if "pckr-gce-ans" in p)
    assert gce
    assert "Systems Manager" not in gce and "ssm-document" not in gce
