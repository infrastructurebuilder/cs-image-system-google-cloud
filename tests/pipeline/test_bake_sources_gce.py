# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The googlecompute sources a bake is emitted from: an image builder's
machine type sits between the image's entry and the runtime (with no type
on the entry, the ``pckr-gce-ans`` builder's ``default_machine_type`` is
the one the image's source bakes on), and on GCE the runtime's disk size
is the bake disk, over the OS builder's.

Carried from cs-image-system-3's ``tests/test_bake_sources.py`` as of
f3c7472e (spec 005, T073):
``test_an_image_builders_machine_type_sits_between_the_entry_and_the_runtime``
and the GCE line of ``test_the_entry_disk_size_is_the_bake_disk_and_the_fingerprints``.
The file's other cases prove the amazon-ebs source, the image variables
and the HCL rendering, and stay there.
"""
from __future__ import annotations

from pathlib import Path

import yaml


def _edit(path: Path, fn) -> None:
    data = yaml.safe_load(path.read_text())
    fn(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def test_an_image_builders_machine_type_sits_between_the_entry_and_the_runtime(family_root, family_run):
    root = family_root
    _edit(root / "cfg" / "image-builders.yml",
          lambda d: next(b for b in d["image_builders"] if b["name"] == "pckr-gce-ans").update(
              default_machine_type="e2-highmem-2"))

    def drop_entry_machine(d):
        dask = next(i for i in d["images"] if i["name"] == "imgfile-basic-dask")
        for r in dask.get("runtimes") or []:
            r.pop("machine_type", None)
            r.pop("default_machine_type", None)
    _edit(root / "images" / "image1.yaml", drop_entry_machine)
    run = family_run(config_root=root)
    assert run.run(["base-image", "instance-image"], apply=False).ok
    src = "".join(p.read_text() for p in run.generated.rglob("*source-imgfile-basic-dask*.pkr.hcl")
                  if "pckr-gce-ans" in str(p))
    assert "e2-highmem-2" in src, src


def test_the_gce_runtimes_disk_size_is_the_bake_disk(family_root, family_run):
    from cs_image_system.base.lineage import bake_disk_size
    run = family_run(config_root=family_root)
    osb = run.ctx.os_builders["basic-rh-10"]
    assert osb.model.default_primary_disk_size not in (None, 10)            # the OS builder has its own
    assert bake_disk_size(run.ctx, osb, "gcloud-east1") == 10               # the runtime wins
    # and over an entry that declares one for this runtime, too
    _edit(family_root / "cfg" / "os-builders.yml",
          lambda d: next(e for e in next(o for o in d["os_builders"] if o["name"] == "basic-rh-10")["runtimes"]
                         if e.get("image_builder") == "pckr-gce-ans").update(default_primary_disk_size=150))
    declared = family_run(config_root=family_root)
    assert bake_disk_size(declared.ctx, declared.ctx.os_builders["basic-rh-10"], "gcloud-east1") == 10
