# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""A configuration names the family's words bare or qualified, as before the
move: the distributions keep their names, so the namespaces derived from
them (``gcloud-runtime``, ``tf-gcp``, ``gcs-state``) stay, and a tree written
against the family in cs-image-system-3 loads unchanged (spec 005, story 3)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from family import FixtureRun, copy_config

#: (file under cfg/, list key, builder name, its qualified type)
QUALIFIED = (
    ("runtime-builders.yml", "runtime_builders", "gcloud-east1", "gcloud-runtime/gcloud"),
    ("instance-builders.yml", "instance_builders", "tofu-gce", "tf-gcp/tofu-gce"),
    ("storage-builders.yml", "storage_builders", "gcp-pd", "tf-gcp/tf-gcp-pd"),
    ("state-backends.yml", "state_backends", "gcs-east1", "gcs-state/gcs"),
)


def _qualify(root: Path) -> None:
    for name, key, builder, word in QUALIFIED:
        path = root / "cfg" / name
        data = yaml.safe_load(path.read_text())
        entry = next(e for e in data[key] if e["name"] == builder)
        entry["type"] = word
        path.write_text(yaml.safe_dump(data, sort_keys=False))


@pytest.mark.parametrize("qualified", [False, True], ids=["bare", "qualified"])
def test_the_family_words_load_bare_and_qualified(tmp_path: Path, monkeypatch, qualified: bool):
    root = copy_config(tmp_path)
    if qualified:
        _qualify(root)
    run = FixtureRun(tmp_path, monkeypatch, config_root=root)
    try:
        ctx = run.ctx
        assert type(ctx.runtime_builders["gcloud-east1"]).__module__.startswith("cs_image_system.gcloud_runtime")
        assert type(ctx.instance_builders["tofu-gce"]).__module__.startswith("cs_image_system.tf_gcp_plugin")
        assert type(ctx.storage_builders["gcp-pd"]).__module__.startswith("cs_image_system.tf_gcp_plugin")
        assert type(ctx.state_backends["gcs-east1"]).__module__.startswith("cs_image_system.gcs_state_plugin")
    finally:
        run.restore_cwd()
