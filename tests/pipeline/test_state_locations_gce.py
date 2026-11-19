# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The family's ``gcs`` state backend registers with its declared bucket
and prefix, gives each root its own object (``<prefix>/<root>/default.tfstate``),
and every run records the family's roots on it; a commented-out
declaration loads as no declaration at all.

Carried from cs-image-system-3's ``tests/test_state_locations.py`` (spec 005,
T024), its gcs case. There the fixture declares ``gcs-east1`` bound to no
root, so the case proved it registers and moves nothing; in the family's
fixture ``gcs-east1`` is the default and every Google Cloud root binds to
it (the operator's decision, research R7), so the case proves the roots'
records instead, with the GCE rows of that file's "every root resolves a
location" case. The collision rule, the resolution chain, the move guard
and the migration are the core's and the Terraform libraries', proven
there on S3 and local backends.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from family import FixtureRun, copy_config

from cs_image_system.hashicorp_utils.collector import terraform_collector

GCS = "gcs://csis-sandbox-tfstate/statefiles/csia"


def _errors(ctx) -> list[str]:
    from cs_image_system.tofu_roots.hooks import state_location_problems
    return [str(e) for e in state_location_problems(ctx)]


def _records(run: FixtureRun) -> dict[str, dict]:
    return yaml.safe_load((run.meta_state / "state-locations.yaml").read_text())["workspaces"]


def test_the_gcs_backend_binds_every_family_root_and_a_commented_declaration_loads_as_nothing(tmp_path: Path, monkeypatch):
    fixture_run = FixtureRun(tmp_path, monkeypatch)
    reg = terraform_collector(fixture_run.ctx).resolve_backend("gcs-east1")
    assert reg is not None and reg.type == "gcs" and reg.settings["bucket"] == "csis-sandbox-tfstate"
    assert str(reg.state_location("gcp-pd")) == f"{GCS}/gcp_pd/default.tfstate"
    assert _errors(fixture_run.ctx) == []
    assert fixture_run.run("all", apply=False).ok
    rec = _records(fixture_run)
    for ws, key in (("gcp-pd", "gcp_pd"), ("gcp-gcs", "gcp_gcs"), ("tofu-gce", "tofu_gce")):
        assert rec[ws] == {"backend": "gcs-east1", "type": "gcs", "location": f"{GCS}/{key}/default.tfstate",
                           "bucket": "csis-sandbox-tfstate", "prefix": f"statefiles/csia/{key}",
                           "run": fixture_run.ctx.run_id}, ws
    # the declaration commented out, line by line (the tree's other backend,
    # local-dev, made the default so the tree still has one): no backend of
    # that name loads, and the roots that name it are refused as naming an
    # undeclared one
    root = copy_config(tmp_path / "commented")
    path = root / "cfg" / "state-backends.yml"
    lines, out, inside = path.read_text().splitlines(), [], False
    for line in lines:
        if line.startswith("- "):
            inside = line == "- name: gcs-east1"
        out.append(f"# {line}" if inside else line)
    text = "\n".join(out) + "\n"
    assert "  path: state\n" in text
    path.write_text(text.replace("  path: state\n", "  path: state\n  is_default: true\n"))
    assert "gcs-east1" not in str(yaml.safe_load(path.read_text()))
    commented = FixtureRun(tmp_path / "commented", monkeypatch, config_root=root)
    assert terraform_collector(commented.ctx).resolve_backend("gcs-east1") is None
    assert any("'gcs-east1'" in e and "not declared" in e for e in _errors(commented.ctx))
