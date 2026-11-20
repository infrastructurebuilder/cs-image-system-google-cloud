# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""A declared output image name, on Google Cloud: the fixture's GCE
prefixes resolve as declared (the entry's over the OS builder's; the
image's default ``<image>-<image builder>``) with no finding; a tree that
declares nothing names a base build ``<OS builder>-<runtime>``; two
prefixes that collapse to one GCE name (GCE lowercases and rewrites what
it cannot keep) are refused as one prefix beginning another; a full name
longer than GCE's 63 characters is refused naming the limit; and the
runtime's own rule takes any case and refuses 64 characters.

Carried from cs-image-system-3's ``tests/test_output_image_name.py`` as of
f3c7472e (spec 005, T073):
``test_two_names_that_collapse_to_one_gce_name_are_refused_and_aws_keeps_case``
(its GCE half: AWS keeping case stays there, in
``test_the_runtime_rules_themselves``), and the GCE halves of
``test_the_fixtures_prefixes_resolve_as_declared_and_have_no_finding``,
``test_a_tree_that_declares_nothing_keeps_todays_names``,
``test_an_images_entry_names_its_builds_and_the_deferred_lookup`` (the GCE
entry keeps the default name; the AWS entry's declaration beside it needs
an AWS runtime this family's fixture does not have),
``test_a_name_the_runtime_cannot_take_is_refused_naming_the_rule`` and
``test_the_runtime_rules_themselves``. The file's other cases (the field,
the timestamp and unrendered-template refusals, the docs) are the core's.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from family import load_context, stub_environment

GCE = "gcloud-east1"


def _edit(path: Path, fn) -> None:
    data = yaml.safe_load(path.read_text())
    fn(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _image_entry(d, image: str, builder: str) -> dict:
    img = next(i for i in d["images"] if i["name"] == image)
    return next(r for r in img["runtimes"] if r.get("image_builder") == builder)


def _declare(root: Path, image: str, builder: str, prefix: str) -> None:
    """Declare ``output_image_name`` on one image's entry, in whichever
    file of the copy's ``images/`` holds the image."""
    for f in sorted((root / "images").glob("*.yaml")):
        if any(i.get("name") == image for i in (yaml.safe_load(f.read_text()) or {}).get("images", [])):
            _edit(f, lambda d: _image_entry(d, image, builder).update(output_image_name=prefix))
            return
    raise AssertionError(f"no image {image} in {root / 'images'}")


def _ctx(root: Path, monkeypatch):
    monkeypatch.chdir(Path.cwd())                               # the load moves the working directory; this restores it
    stub_environment(monkeypatch)
    return load_context(root)


def _names(ctx, runtime: str) -> dict[str, tuple[str, bool]]:
    from cs_image_system.base.image_names import output_names_by_runtime
    return {who: (prefix, declared) for who, prefix, declared in output_names_by_runtime(ctx)[runtime]}


def _findings(ctx) -> list[str]:
    from cs_image_system.engine.commands.validate import check_image_names
    return [str(e) for e in check_image_names(ctx)]


def test_the_fixtures_gce_prefixes_resolve_as_declared_and_have_no_finding(family_root, monkeypatch):
    ctx = _ctx(family_root, monkeypatch)
    gce = _names(ctx, GCE)
    assert gce["OS builder 'basic-rh-10'"] == ("noscsb-gcp-rh10-gcp-my-rh10", True)     # the entry's, over the builder's
    assert gce["image 'imgfile-basic-dask'"] == ("imgfile-basic-dask-pckr-gce-ans", False)
    assert ctx.images_map["imgfile-basic-dask"]._runtime_map[GCE].get_image_output_name() == "imgfile-basic-dask-pckr-gce-ans"
    assert _findings(ctx) == []


def test_a_tree_that_declares_nothing_keeps_todays_gce_names(family_root, monkeypatch):
    root = family_root
    f = root / "cfg" / "os-builders.yml"
    f.write_text(re.sub(r"^\s+output_image_name: .*\n", "", f.read_text(), flags=re.M))
    ctx = _ctx(root, monkeypatch)
    assert _names(ctx, GCE)["OS builder 'basic-rh-10'"] == (f"basic-rh-10-{GCE}", False)
    assert _names(ctx, GCE)["image 'imgfile-basic-dask'"] == ("imgfile-basic-dask-pckr-gce-ans", False)
    assert _findings(ctx) == []


def test_two_names_that_collapse_to_one_gce_name_are_refused(family_root, monkeypatch):
    root = family_root
    _declare(root, "imgfile-basic-dask", "pckr-gce-ans", "NOSCSB.GCP.RH10.GCP.MY.RH10")
    ctx = _ctx(root, monkeypatch)
    found = _findings(ctx)
    assert len(found) == 1, found
    assert f"OS builder 'basic-rh-10' and image 'imgfile-basic-dask' on runtime {GCE}" in found[0]
    assert "collapse" in found[0]
    assert ctx.runtime_builders[GCE].image_name_as_made("NOSCSB.GCP.RH10.GCP.MY.RH10") == "noscsb-gcp-rh10-gcp-my-rh10"


def test_a_name_longer_than_gce_takes_is_refused_naming_the_limit(family_root, monkeypatch):
    root = family_root
    _declare(root, "imgfile-basic-dask", "pckr-gce-ans", "x" * 60)
    ctx = _ctx(root, monkeypatch)
    found = _findings(ctx)
    assert len(found) == 1, found
    assert f"on runtime {GCE}" in found[0] and "63" in found[0]


def test_the_gce_rule_itself():
    from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder
    gce_rule = GCPCloudBuilder.image_name_problem
    assert gce_rule(None, "Any Case Is Fine-20260826-120000") is None     # type: ignore[arg-type]
    assert gce_rule(None, "a" * 64) is not None                           # type: ignore[arg-type]
