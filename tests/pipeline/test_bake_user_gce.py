# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The bake user on Google Cloud: the GCE entry's ``ssh_username`` is the
fixture's user for the OS builder and, through its root, for the image;
the entry beats the runtime's ``ssh_username``; a GCE chain bakes and
provisions as one user (the googlecompute source and the ansible
provisioner name the same one), and an image naming another user than its
root is refused at validate; the Google Cloud packer source emits what the
resolver answers and carries no fallback of its own.

Carried from cs-image-system-3's ``tests/test_bake_user.py`` as of f3c7472e
(spec 005, T073): ``test_the_entry_beats_the_runtimes_ssh_username``,
``test_the_gce_provisioner_connects_as_the_user_the_source_bakes_as``,
``test_a_gce_image_naming_another_user_than_its_root_is_refused``, and the
GCE halves of ``test_the_fixture_resolves_as_it_always_baked`` and
``test_the_resolver_is_what_both_sources_emit``. The file's other cases
(the ``config_username`` fields, the runtime's fallback and owners, the
refusal of nothing to name a user) are the core's on the AWS runtime and
stay there; so does the refused pair's AWS half ("the same pair on AWS is
allowed"), which needs an AWS runtime this family's fixture does not have.
"""
from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import yaml
from family import load_context, stub_environment

GCE = "gcloud-east1"


def _edit(path: Path, fn) -> None:
    data = yaml.safe_load(path.read_text())
    fn(data)
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def _osb(data: dict, name: str) -> dict:
    return next(o for o in data["os_builders"] if o["name"] == name)


def _entry(osb: dict, image_builder: str) -> dict:
    return next(e for e in osb["runtimes"] if e.get("image_builder") == image_builder)


def _runtime(data: dict, name: str) -> dict:
    return next(r for r in data["runtime_builders"] if r["name"] == name)


def _ctx(root: Path, monkeypatch) -> Any:
    monkeypatch.chdir(Path.cwd())                               # the load moves the working directory; this restores it
    stub_environment(monkeypatch)
    return load_context(root)


def _resolve(ctx: Any, image_name: str, runtime: str) -> str:
    from cs_image_system.base.bake_user import entry_for_runtime, resolve_bake_user, resolve_for_entry
    if image_name in ctx.os_builders:
        osb = ctx.os_builders[image_name]
        return resolve_for_entry(ctx, osb, entry_for_runtime(ctx, osb, runtime), runtime)
    return resolve_bake_user(ctx, ctx.images_map[image_name], runtime)


def test_the_fixture_resolves_as_it_always_baked(family_root, monkeypatch):
    """Pins what held: the golden did not move, and these are its users."""
    ctx = _ctx(family_root, monkeypatch)
    assert _resolve(ctx, "basic-rh-10", GCE) == "packer"           # the entry
    assert _resolve(ctx, "imgfile-basic-dask", GCE) == "packer"    # via its root


def test_the_entry_beats_the_runtimes_ssh_username(family_root, monkeypatch):
    root = family_root
    _edit(root / "cfg" / "runtime-builders.yml", lambda d: _runtime(d, GCE).update(ssh_username="runtime-user"))
    ctx = _ctx(root, monkeypatch)
    # the GCE entry declares `packer`; the runtime's value used to override it
    assert _resolve(ctx, "basic-rh-10", GCE) == "packer"


def test_the_gce_provisioner_connects_as_the_user_the_source_bakes_as(family_root, family_run):
    root = family_root
    _edit(root / "cfg" / "os-builders.yml",
          lambda d: _entry(_osb(d, "basic-rh-10"), "pckr-gce-ans").update(ssh_username="builder"))
    run = family_run(config_root=root)
    assert run.run(["base-image", "instance-image"], apply=False).ok
    gce = "".join(p.read_text() for p in run.generated.rglob("*.pkr.hcl") if "pckr-gce-ans" in str(p))
    assert 'ssh_username = "builder"' in gce, "the source bakes as the entry's user"
    assert 'user = "builder"' in gce and 'user = "packer"' not in gce, \
        "the ansible provisioner connects as the same user (it said packer)"


def test_a_gce_image_naming_another_user_than_its_root_is_refused(family_root, monkeypatch):
    from cs_image_system.engine.commands.validate import check_bake_users
    root = family_root

    def edit(d):
        dask = next(i for i in d["images"] if i["name"] == "imgfile-basic-dask")
        next(r for r in dask["runtimes"] if r["image_builder"] == "pckr-gce-ans")["ssh_username"] = "other"
    _edit(root / "images" / "image1.yaml", edit)
    ctx = _ctx(root, monkeypatch)
    errors = [str(e) for e in check_bake_users(ctx)]
    assert any("imgfile-basic-dask" in e and "'other'" in e and GCE in e
               and "'basic-rh-10'" in e and "'packer'" in e for e in errors), errors


def test_the_resolver_is_what_the_gce_source_emits():
    """The Google Cloud packer source carries no fallback of its own."""
    from cs_image_system.gcloud_runtime import gcp_packer_source
    src = inspect.getsource(gcp_packer_source)
    assert "resolve_bake_user(" in src and "model.ssh_username" not in src, gcp_packer_source.__name__
