# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""Compute Engine's power states in the system's words: each raw GCE status
maps onto the shared vocabulary, and GCE's ``TERMINATED`` is a machine
that is stopped and can be started again, never one that is gone.

Carried from cs-image-system-3's ``tests/test_power_state.py`` (spec 005,
T024). The vocabulary, the bounded start and "off is not drift" are the
core's and stay there; so do EC2's mappings and the EC2 half of the
``terminated`` comparison.
"""
from __future__ import annotations

import pytest

from cs_image_system.contract import power_state as ps  # the vocabulary is the contract's; the kit re-exports it
from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder


@pytest.mark.parametrize(("raw", "expected"), [
    ("RUNNING", ps.RUNNING),
    ("PROVISIONING", ps.STARTING),
    ("STAGING", ps.STARTING),
    ("SUSPENDED", ps.SUSPENDED),
    ("TERMINATED", ps.STOPPED),
])
def test_gce_states_map_onto_our_words(raw, expected):
    assert GCPCloudBuilder._GCE_POWER[raw] == expected


def test_gce_terminated_means_stopped_not_gone():
    """The trap the shared vocabulary exists to defuse: on GCE TERMINATED is
    a machine that can be started again (on EC2 the same word is a machine
    that no longer exists, which cs-image-system-3 proves)."""
    assert GCPCloudBuilder._GCE_POWER["TERMINATED"] == ps.STOPPED
    assert ps.exists(GCPCloudBuilder._GCE_POWER["TERMINATED"])
