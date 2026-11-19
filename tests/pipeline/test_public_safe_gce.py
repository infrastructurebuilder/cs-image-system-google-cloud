# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The commit-time gate refuses a Google Cloud service-account key: the
gcloud runtime plugin contributes the ``gcp-service-account`` shape
(``secret_patterns()``), the scanner holds it as a hard rule beside its
own, and it fires anywhere, prose and test code included, but not on the
word ``service_account`` alone.

Carried from cs-image-system-3's ``tests/test_public_safe.py`` (spec 005,
T024): the ``gcp-service-account`` rows of its hard-shape and
negative-shape cases. The scanner's own rules, the allow list, the tree
and index scans and the commit refusal are the core's and stay there.

The fake key below is built by concatenation, so this module never carries
the shape the gate scans test code for.
"""
from __future__ import annotations

from cs_image_system.engine.public_safe import hard_rules, scan_bytes
from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder

RULE = "gcp-service-account"
KEY_FILE = '{"ty' + 'pe": "service_account", "private_' + 'key": "x", "private_' + 'key_id": "' + "a" * 40 + '"}'
PROSE = '"ty' + 'pe": "service_account" in prose'


def rules(data: str, path: str = "generated/x.tf") -> set[str]:
    return {f.rule for f in scan_bytes(data.encode(), path)}


def test_the_gcloud_plugin_contributes_the_service_account_shape_as_a_hard_rule():
    assert RULE in GCPCloudBuilder.secret_patterns()
    assert RULE in hard_rules()


def test_a_service_account_key_is_refused_anywhere_including_prose_and_test_code():
    assert RULE in rules(KEY_FILE)
    assert RULE in rules(KEY_FILE, "README.md")
    assert RULE in rules(KEY_FILE, "tests/test_x.py")


def test_the_service_account_rule_does_not_fire_on_the_word_alone():
    assert RULE not in rules(PROSE)
