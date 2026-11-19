# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""What the GCP section of the bootstrap root makes or reads of the GCS
state bucket, and says so: an absent bucket is MADE (managed, in the
runtime's region, uniform access, public access prevented, single IAM
members, never an authoritative binding), with the root's state local
first; a bucket that stands is READ, never managed, and the root binds to
it. The release carries the ``bootstrap_gcp`` module's three files.

Carried from cs-image-system-3's ``tests/test_bootstrap_coverage.py``
(spec 005, T024): its GCS bucket case, and the ``bootstrap_gcp`` half of
its release-carries-the-modules case. The S3 buckets, the audit table
across sections, the Okta audit and the AWS write role stay there. The
helpers ``_facts``, ``_project`` and ``_tree`` are
``tests/pipeline/test_bootstrap_gcp.py``'s, as they were
``tests/test_bootstrap_gcp.py``'s there.
"""
from __future__ import annotations

import re
from pathlib import Path

from family import module_path
from starter_support import _assigned
from test_bootstrap_gcp import _facts as _gcp_facts
from test_bootstrap_gcp import _project, _tree

from cs_image_system.engine import bootstrap as bs


def _row(readme: str, section: str, resource: str, status: str) -> bool:
    """A row of the README's coverage table: `| <section> | ...<resource>... | <status> |`."""
    return re.search(rf"^\| {section} \| [^|]*{re.escape(resource)}[^|]* \| {status} \|", readme, flags=re.M) is not None


def _gce_root(tmp_path: Path, bucket_exists: bool) -> tuple[Path, Path]:
    root = _tree(tmp_path)
    facts = _gcp_facts(root, _project(None, number=True, pool=False, provider=False, read=False, write=False, bucket=bucket_exists))
    answers = bs.run_interview(bs.discover(), facts, quiet=True, only=["github", "gcp"])
    bs.write_answers(root / bs.ANSWERS_FILE, answers)
    assert bs.regenerate(root)
    return root, bs.output_dir(root)


def test_the_gcs_state_bucket_is_made_when_absent_and_read_when_it_stands(tmp_path: Path):
    root, out = _gce_root(tmp_path, bucket_exists=False)
    answers = bs.read_answers(root / bs.ANSWERS_FILE)["gcp"]
    assert answers["state_bucket_exists"] is False and answers["state_bucket_managed"] is True
    assert answers["state_bucket_location"] == "us-east1"                     # the runtime's zone's region
    tfvars = (out / "bootstrap.auto.tfvars").read_text()
    for key, value in (("gcp_state_bucket", '"acme-gcs-tfstate"'), ("gcp_state_bucket_managed", "true"),
                       ("gcp_state_bucket_exists", "false"), ("gcp_state_bucket_location", '"us-east1"'),
                       ("gcp_state_prefix", '"statefiles/my-team-images"')):
        assert _assigned(tfvars, key, value), key
    assert 'backend "local" {}' in (out / "providers.tf").read_text()        # local first, as on AWS
    readme = (out / "README.md").read_text()
    assert "us-east1" in readme and _row(readme, "gcp", "acme-gcs-tfstate", "MADE"), readme
    module = (module_path("bootstrap_gcp") / "main.tf").read_text()
    for needle in ('resource "google_storage_bucket" "state"', "uniform_bucket_level_access = true",
                   'public_access_prevention    = "enforced"', 'resource "google_storage_bucket_iam_member" "state_read"',
                   'resource "google_storage_bucket_iam_member" "state_write"', "roles/storage.objectViewer"):
        assert needle in module, needle
    assert not re.search(r"google_storage_bucket_iam_(binding|policy)\b", module)   # single members, never authoritative
    # the bucket stands: read, never managed; the root binds to it
    root, out = _gce_root(tmp_path / "b", bucket_exists=True)
    answers = bs.read_answers(root / bs.ANSWERS_FILE)["gcp"]
    assert answers["state_bucket_exists"] is True and answers["state_bucket_managed"] is False
    assert 'backend "gcs" {' in (out / "providers.tf").read_text()
    assert _row((out / "README.md").read_text(), "gcp", "acme-gcs-tfstate", "READ")


def test_the_release_carries_the_bootstrap_gcp_module():
    assert [f.name for f in sorted(module_path("bootstrap_gcp").glob("*.tf"))] == ["main.tf", "outputs.tf", "variables.tf"]
