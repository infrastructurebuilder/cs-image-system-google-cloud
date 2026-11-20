# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The machine type of a GCE instance is a launch parameter: one that
declares none launches on the runtime's default, and the GCE builder
honours a declared ``machine_type`` in the emitted root and in the launch
parameters.

Carried from cs-image-system-3's ``tests/test_machine_type.py`` as of
f3c7472e (spec 005, T073): ``test_the_gce_builder_honours_a_declared_machine_type``
and the GCE half of ``test_the_machine_type_is_a_launch_parameter``. The
file's other cases (a resize in place, a change riding along with it
refused, an old record adopting the key) prove the core on the AWS runtime
and stay there.
"""
from __future__ import annotations

import yaml

from cs_image_system.base import launch_params as lp


def _declare(root, instance: str, **fields) -> None:
    p = root / "instances" / "instances.yaml"
    d = yaml.safe_load(p.read_text())
    for i in d["instances"]:
        if i["name"] == instance:
            i.update(fields)
    p.write_text(yaml.safe_dump(d, sort_keys=False))


def test_an_undeclared_gce_machine_type_is_the_runtimes_default(family_run):
    run = family_run()
    by_name = {i.get_name(): i for i in run.ctx.instances}
    gce = lp.compute_launch_params(run.ctx, by_name["gce-test"])
    assert gce["machine_type"] == run.ctx.runtime_builders["gcloud-east1"].get_default_machine_type()   # the default


def test_the_gce_builder_honours_a_declared_machine_type(family_root, family_run):
    root = family_root
    _declare(root, "gce-test", machine_type="e2-small")
    run = family_run(config_root=root)
    summary = run.run(["instance-image"], apply=False, only=["none"])
    assert summary.ok, summary.validation_errors or summary.error
    tf = "\n".join(p.read_text() for p in (run.generated / "instance-image" / "tofu-gce").rglob("*.tf"))
    assert '"e2-small"' in tf and '"e2-micro"' not in tf.split('module "instance_gce_test"', 1)[1].split("\n}", 1)[0]
    by_name = {i.get_name(): i for i in run.ctx.instances}
    assert lp.compute_launch_params(run.ctx, by_name["gce-test"])["machine_type"] == "e2-small"
