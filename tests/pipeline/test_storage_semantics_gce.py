# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Storage semantics on the family's storage roots (the operator's ruling:
a storage exists exactly as long as its declaration).

* a persistent disk declared ``archived`` is snapshotted first, then
  destroyed; declared active again it is created from the snapshot, and the
  snapshot deleted after the apply; an archived disk declared destroyed
  deletes its archive and whitelists nothing;
* an undeclared GCS bucket is a whitelisted destroy, wiped first by its
  generated script, recorded with action ``undeclared``;
* a re-declared persistent disk with a tombstone is a new generation.

Carried from cs-image-system-3's ``tests/test_storage_semantics.py``
(spec 005, T024). The EBS archive cases, EFS's refusal to archive, the
single-attach refusal, the data lifecycles (S3 and EFS) and the instance
root's cross-backend storage read are AWS's and stay there; of the
undeclared-storage case only its GCS half is carried.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from family import FixtureRun, command_lines, copy_config

from cs_image_system.contract.lifecycles import Lifecycle
from cs_image_system.engine.read_models import record_storage_transitions


def _record(root: Path, name: str, state: str, facts: dict | None = None, generation: int = 1) -> None:
    ms = root / "meta-state"
    ms.mkdir(exist_ok=True)
    p = ms / "storage-state.yaml"
    data = yaml.safe_load(p.read_text()) if p.exists() else {}
    data.setdefault("storages", {})[name] = {
        "state": state, "generation": generation,
        "history": [{"from": None, "to": "active", "run": "r0", "generation": 1}]
        + ([{"from": "active", "to": "destroyed", "run": "r1", "generation": 1}] if state == "destroyed" else []),
        **({"facts": facts} if facts else {}),
    }
    p.write_text(yaml.safe_dump(data, sort_keys=True))


def _undeclare_storage(root: Path, name: str) -> None:
    for p in (root / "storages").glob("*.y*ml"):
        d = yaml.safe_load(p.read_text()) or {}
        before = len(d.get("storages") or [])
        d["storages"] = [s for s in (d.get("storages") or []) if s.get("name") != name]
        if len(d["storages"]) != before:
            p.write_text(yaml.safe_dump(d, sort_keys=False))


def _undeclare_instance(root: Path, *names: str) -> None:
    p = root / "instances" / "instances.yaml"
    d = yaml.safe_load(p.read_text()) or {}
    d["instances"] = [i for i in (d.get("instances") or []) if i["name"] not in names]
    p.write_text(yaml.safe_dump(d, sort_keys=False))


def _set_storage_state(root: Path, name: str, state: str) -> None:
    for p in (root / "storages").glob("*.y*ml"):
        d = yaml.safe_load(p.read_text()) or {}
        changed = False
        for s in d.get("storages") or []:
            if s.get("name") == name:
                s["state"] = state
                changed = True
        if changed:
            p.write_text(yaml.safe_dump(d, sort_keys=False))


def _gates(script: str) -> dict[str, str]:
    out = {}
    for line in command_lines(script):
        if "gate-plan" in line:
            out[line.split('"')[1]] = line
    return out


def _pd_lines(run: FixtureRun) -> list[str]:
    return [ln for ln in command_lines((run.generated / "storage" / "run-storage.sh").read_text())
            if ln.split('"')[1] == "gcp-pd/storage-generation"]


@pytest.fixture
def prepared(tmp_path: Path, monkeypatch):
    """A private copy of the fixture as it stands (``gce-test`` NOT
    ephemeral, unlike the conftest's ``prepared``) and a run factory."""
    root = copy_config(tmp_path)
    runs: list[FixtureRun] = []

    def make(**kw) -> FixtureRun:
        run = FixtureRun(tmp_path, monkeypatch, config_root=root, **kw)
        runs.append(run)
        return run
    try:
        yield root, make
    finally:
        for r in runs:
            r.restore_cwd()


# ---------------------------------------------------------------- declaration and demise

def test_a_declared_storage_with_a_tombstone_is_a_new_generation(prepared):
    root, make = prepared
    _record(root, "gce_data", "destroyed", {"builder": "gcp-pd", "type": "pd"})
    run = make()
    summary = run.run(["storage"], apply=True)          # no "cannot be resurrected"
    assert summary.ok, summary.error
    tf = "\n".join(p.read_text() for p in (run.generated / "storage" / "gcp-pd").rglob("*.tf"))
    assert 'module "storage_gce_data"' in tf              # created again
    run.ctx.config["apply_storage"] = ["gcloud-east1"]
    record_storage_transitions(run.ctx, Lifecycle.STORAGE)
    ms = run.ctx.meta_state
    assert ms.storage_state("gce_data") == "active"
    assert ms.storage_generation("gce_data") == 2
    last = ms.storage_states()["gce_data"]["history"][-1]
    assert last["action"] == "regenerate" and last["generation"] == 2
    assert ms.storage_read_model()["storages"]["gce_data"]["generation"] == 2


def test_an_undeclared_storage_is_a_whitelisted_destroy_with_its_wipe(prepared):
    root, make = prepared
    _record(root, "gce_bucket", "active",
            {"builder": "gcp-gcs", "type": "gcs", "bucket_name": "csis-sandbox-86233086783-default-bucket"})
    _undeclare_storage(root, "gce_bucket")
    run = make()
    assert not any(s.get_name() == "gce_bucket" for s in run.ctx.storages)
    summary = run.run(["storage"], apply=True)
    assert summary.ok, summary.error                     # N22 is gone: not an error
    script = (run.generated / "storage" / "run-storage.sh").read_text()
    gates = _gates(script)
    assert "--allow-destroy module.storage_gce_bucket" in gates["gcp-gcs/storage-generation"]
    assert "bash wipe-gce_bucket.sh" in script
    wipe = (run.generated / "storage" / "gcp-gcs" / "storage-generation" / "wipe-gce_bucket.sh").read_text()
    assert "gs://csis-sandbox-86233086783-default-bucket/**" in wipe
    # the module call is absent (that IS the destroy); the root still exists
    tf = "\n".join(p.read_text() for p in (run.generated / "storage" / "gcp-gcs").rglob("*.tf"))
    assert 'module "storage_gce_bucket"' not in tf and "backend" in tf
    run.ctx.config["apply_storage"] = ["gcp-gcs"]        # only the bucket's root applied
    record_storage_transitions(run.ctx, Lifecycle.STORAGE)
    ms = run.ctx.meta_state
    assert ms.storage_state("gce_bucket") == "destroyed"
    assert ms.storage_states()["gce_bucket"]["history"][-1]["action"] == "undeclared"


# ---------------------------------------------------------------- archived

def test_archiving_a_pd_snapshots_first_and_destroys_the_disk(prepared):
    root, make = prepared
    _undeclare_instance(root, "gce-test")                  # archived requires no attachments (N21)
    _record(root, "gce_data", "active", {"builder": "gcp-pd", "type": "pd"})
    _set_storage_state(root, "gce_data", "archived")
    run = make()
    summary = run.run(["storage"], apply=True)
    assert summary.ok, summary.validation_errors or summary.error
    lines = _pd_lines(run)
    archive = next(i for i, ln in enumerate(lines) if "bash archive-gce-data.sh" in ln)
    plan = next(i for i, ln in enumerate(lines) if "plan -input=false" in ln)
    assert archive < plan
    assert "--allow-destroy module.storage_gce_data" in next(ln for ln in lines if "gate-plan" in ln)
    body = (run.generated / "storage" / "gcp-pd" / "storage-generation" / "archive-gce-data.sh").read_text()
    assert 'gcloud compute disks snapshot "gce-data" --snapshot-names "csis-gce-data-archive"' in body
    assert "already exists" in body                        # idempotent across attempts
    tf = "\n".join(p.read_text() for p in (run.generated / "storage" / "gcp-pd").rglob("*.tf"))
    assert 'module "storage_gce_data"' not in tf and "ARCHIVED" in tf
    # the recorded transition carries the archive name
    run.ctx.config["apply_storage"] = ["gcloud-east1"]
    record_storage_transitions(run.ctx, Lifecycle.STORAGE)
    entry = run.ctx.meta_state.storage_states()["gce_data"]
    assert entry["state"] == "archived" and entry["facts"]["archive"] == "csis-gce-data-archive"


def test_restoring_a_pd_creates_it_from_the_snapshot_then_deletes_the_snapshot(prepared):
    root, make = prepared
    _record(root, "gce_data", "archived", {"builder": "gcp-pd", "type": "pd", "archive": "csis-gce-data-archive"})
    run = make()                                            # declared active (the fixture)
    run.ctx.config["apply_storage"] = ["gcloud-east1"]
    summary = run.run(["storage"], apply=True)
    assert summary.ok, summary.validation_errors or summary.error
    tf = "\n".join(p.read_text() for p in (run.generated / "storage" / "gcp-pd").rglob("*.tf"))
    assert 'snapshot = "csis-gce-data-archive"' in tf
    lines = _pd_lines(run)
    apply_i = next(i for i, ln in enumerate(lines) if "apply -input=false tfplan" in ln)
    restore = next(i for i, ln in enumerate(lines) if "bash restore-gce-data.sh" in ln)
    assert restore > apply_i
    body = (run.generated / "storage" / "gcp-pd" / "storage-generation" / "restore-gce-data.sh").read_text()
    assert 'gcloud compute snapshots delete "csis-gce-data-archive"' in body
    assert "--allow-destroy" not in next(ln for ln in lines if "gate-plan" in ln)


def test_destroying_an_archived_pd_deletes_the_archive_and_whitelists_nothing(prepared):
    root, make = prepared
    _undeclare_instance(root, "gce-test")
    _record(root, "gce_data", "archived", {"builder": "gcp-pd", "type": "pd", "archive": "csis-gce-data-archive"})
    _set_storage_state(root, "gce_data", "destroyed")
    run = make()
    summary = run.run(["storage"], apply=True)
    assert summary.ok, summary.validation_errors or summary.error
    lines = _pd_lines(run)
    assert any("bash unarchive-gce-data.sh" in ln for ln in lines)
    assert "--allow-destroy" not in next(ln for ln in lines if "gate-plan" in ln)   # no disk to destroy
