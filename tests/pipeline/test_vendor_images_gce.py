# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""A pinned GCE vendor image that is not READY is refused: the Google
Cloud runtime's ``query_provider_image_by_id`` raises on an image whose
status is PENDING and returns the image once it is READY.

Carried from cs-image-system-3's ``tests/test_vendor_images.py`` as of
f3c7472e (spec 005, T072). The file's other cases (a vendor move named and
not drift, CI's runtime-unchanged guard, validate's stand-in and family
warning) prove the core and stay there.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from family import copy_config, load_context, stub_environment

from cs_image_system.gcloud_runtime import gcp_runtime_builders as g

SELF_LINK = "https://x/projects/almalinux-cloud/global/images/almalinux-10-x"


def test_a_pinned_gce_image_that_is_not_ready_is_refused(tmp_path: Path, monkeypatch):
    stub_environment(monkeypatch)
    ctx = load_context(copy_config(tmp_path))
    rtb = cast(Any, ctx.runtime_builders["gcloud-east1"])
    entry = next(e for e in ctx.os_builders["basic-rh-10"].get_configs_for_image_builders().values()
                 if e.get_image_builder() == "pckr-gce-ans")
    monkeypatch.setattr(g, "query_image", lambda **kw: {"name": "almalinux-10-x", "status": "PENDING",
                                                          "self_link": SELF_LINK})
    with pytest.raises(ValueError, match="PENDING"):
        g.GCPCloudBuilder.query_provider_image_by_id(rtb, entry, "almalinux-10-x")
    monkeypatch.setattr(g, "query_image", lambda **kw: {"name": "almalinux-10-x", "status": "READY",
                                                          "self_link": SELF_LINK})
    found = g.GCPCloudBuilder.query_provider_image_by_id(rtb, entry, "almalinux-10-x")
    assert found is not None and found[0] == "almalinux-10-x"
