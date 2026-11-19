# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The gcloud runtime's part of the image-source catalog and its
translation of the system's query vocabulary.

The plugin ships, as package data, exactly the ``gcloud`` blocks the
catalog held when it was one file of the core (five families, each with
what it IS and a description), and only ``gcloud`` blocks; a run's catalog
answers them for the tree's OS builder; the effective query of the GCE
entry is the catalog's block, which the runtime translates into Compute
Engine's words; ``validate`` prints that query in both vocabularies and
refuses a key the runtime cannot translate, naming the entry.

Carried from cs-image-system-3's ``tests/test_image_sources.py`` (spec 005,
T024): the ``gcloud`` rows and the GCE halves of its cases. The
vocabulary, the layering, the merge and its conflicts, the stand-in (a
docker runtime) and the type rules are the core's or other families' and
stay there. The family's fixture declares no tree layer
(``cfg/image-sources*.yml``), so the release's blocks answer alone.
"""
from __future__ import annotations

import importlib
import logging
from pathlib import Path

import pytest
import yaml
from family import FIXTURE_CONFIG, copy_config, load_context, stub_environment

from cs_image_system.contract.image import QUERY_KEYS, ImageQuery

GCE_RUNTIME = "gcloud-east1"

#: the ``gcloud`` rows of what the release catalog carried when it was one
#: file in the base package (cs-image-system-3's CATALOG_BEFORE_THE_SPLIT):
#: the plugin's part must lose none of them and invent none
GCLOUD_BEFORE_THE_SPLIT: list[tuple[str, tuple[str, ...], dict]] = [
    ('rhel', (), {'publisher': ['rhel-cloud'], 'family': 'rhel-{version}'}),
    ('alma-linux', (), {'publisher': ['almalinux-cloud'], 'family': 'almalinux-{version}'}),
    ('rocky-linux', (), {'publisher': ['rocky-linux-cloud'], 'family': 'rocky-linux-{version}'}),
    ('centos-stream', (), {'publisher': ['centos-cloud'], 'family': 'centos-stream-{version}'}),
    ('debian', (), {'publisher': ['debian-cloud'], 'family': 'debian-{version}'}),
]
#: what each family said it IS before the split
IS_BEFORE_THE_SPLIT = {"alma-linux": "rhel", "rocky-linux": "rhel", "centos-stream": "rhel"}


def _block(cat, family: str, version: str, runtime_type: str) -> ImageQuery:
    block = cat.block(family, version, runtime_type)
    assert block is not None, (family, version, runtime_type)
    return block


def _entry(ctx, osb_name: str, image_builder: str):
    osb = ctx.os_builders[osb_name]
    return next(e for e in osb.get_configs_for_image_builders().values() if e.get_image_builder() == image_builder)


def _edit_os_builders(root: Path, change) -> None:
    p = root / "cfg" / "os-builders.yml"
    doc = yaml.safe_load(p.read_text())
    change(doc["os_builders"])
    p.write_text(yaml.safe_dump(doc, sort_keys=False))


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.chdir(Path.cwd())                     # the load moves the working directory; this restores it
    stub_environment(monkeypatch)
    return load_context(copy_config(tmp_path))


# ------------------------------------------------------------- the plugin's part

def test_the_gcloud_part_holds_exactly_what_the_one_file_held_for_gcloud():
    from cs_image_system.base.image_sources import packaged_default_entries
    from cs_image_system.engine.loader import installed_registry
    entries = packaged_default_entries(installed_registry().runtime_builder_classes())
    merged = {(e.family, tuple(e.versions)) for e in entries if "gcloud" in e.sources}
    assert merged == {(f, v) for f, v, _ in GCLOUD_BEFORE_THE_SPLIT}
    for f, v, q in GCLOUD_BEFORE_THE_SPLIT:
        entry = next(e for e in entries if e.family == f and tuple(e.versions) == v)
        assert entry.sources["gcloud"] == q, (f, v)
        assert entry.is_ == IS_BEFORE_THE_SPLIT.get(f), f
        assert entry.description, (f, v)                     # every family keeps a description


def test_the_gcloud_runtime_ships_only_its_own_blocks():
    from cs_image_system.base.image_sources import structure_entries
    package, runtime_type = "cs_image_system.gcloud_runtime.gcp_runtime_builders", "gcloud"
    module = importlib.import_module(package)
    cls = next(c for c in vars(module).values()
               if isinstance(c, type) and getattr(c, "csis_name", None) and c.__module__ == package
               and "Builder" in c.__name__ and not c.__name__.endswith(("Checker", "Model"))
               and c.csis_name() == runtime_type)
    raw = cls.image_source_entries()
    assert raw, f"{runtime_type} ships no catalog entries"
    entries = structure_entries(list(raw), where=runtime_type)
    assert all(e.runtime_types() == [runtime_type] for e in entries), [(e.family, e.runtime_types()) for e in entries]
    assert {f for f, _, _ in GCLOUD_BEFORE_THE_SPLIT} == {e.family for e in entries}


def test_the_runs_catalog_answers_the_gcloud_blocks(ctx):
    cat = ctx.image_sources   # the run's: no tree layer here, the release's alone
    assert _block(cat, "debian", "12", "gcloud").family == "debian-12"
    assert _block(cat, "alma-linux", "10", "gcloud").to_mapping() == {"family": "almalinux-10", "publisher": ["almalinux-cloud"]}
    assert cat.block("ubuntu", "24", "gcloud") is None                                     # GCE: declare it


# ------------------------------------------------------------------- the stack

def test_the_effective_query_is_the_catalog_under_the_declarations(ctx):
    gce = _entry(ctx, "basic-rh-10", "pckr-gce-ans")
    assert gce.runtime_type() == "gcloud"
    assert gce.image_query().to_mapping() == {"family": "almalinux-10", "publisher": ["almalinux-cloud"]}


def test_the_gce_runtime_translates_the_query_into_its_own_words(ctx):
    gce = ctx.runtime_builders[GCE_RUNTIME]
    native = gce.translate_image_query(_entry(ctx, "basic-rh-10", "pckr-gce-ans").image_query())
    assert native["projects"] == ["almalinux-cloud"] and native["terms"] == {"family": "almalinux-10", "status": "READY"}
    assert native["filter"] == '(family = "almalinux-10") AND (status = "READY")'
    assert "root_device" not in gce.supported_query_keys()
    assert "family" in gce.supported_query_keys()
    assert set(QUERY_KEYS) > gce.supported_query_keys()


# ----------------------------------------------------------------- validation

def test_validate_prints_the_gce_query_in_both_vocabularies(ctx, caplog):
    from cs_image_system.engine.commands.validate import check_image_sources
    with caplog.at_level(logging.INFO, logger="cs_image_system.engine.commands.validate"):
        assert check_image_sources(ctx) == []
    lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("image source:")]
    assert any(f"on runtime {GCE_RUNTIME} (gcloud): family=almalinux-10" in ln for ln in lines), lines
    declared = {rt["name"] for rt in yaml.safe_load((FIXTURE_CONFIG / "cfg" / "runtime-builders.yml").read_text())["runtime_builders"]}
    named = {ln.split(" on runtime ")[1].split(" ")[0] for ln in lines}
    assert named <= declared and GCE_RUNTIME in named, lines   # one line per (OS builder, runtime)


def test_validate_refuses_a_key_the_runtime_cannot_translate(tmp_path, monkeypatch):
    from cs_image_system.engine.commands.validate import check_image_sources
    monkeypatch.chdir(Path.cwd())
    stub_environment(monkeypatch)
    root = copy_config(tmp_path)

    def change(entries):
        rh = next(e for e in entries if e["name"] == "basic-rh-10")
        next(r for r in rh["runtimes"] if r["name"] == "gcp-my-rh10")["query"] = {"filters": {"root_device_type": "ebs"}}
    _edit_os_builders(root, change)
    errors = [str(e) for e in check_image_sources(load_context(root))]
    assert len(errors) == 1 and "basic-rh-10" in errors[0] and "(gcloud)" in errors[0]
    assert "cannot translate image query key(s) root_device" in errors[0] and "native:" in errors[0]
