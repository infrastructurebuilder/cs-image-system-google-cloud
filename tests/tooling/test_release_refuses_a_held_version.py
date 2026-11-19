# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""A release of the family never reuses a version an index has listed for
any of its three names, and never guesses when the index cannot be asked.
The index is answered by a stand-in; nothing reaches the network."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "release"


def _release():
    loader = importlib.machinery.SourceFileLoader("family_release", str(SCRIPT))
    spec = importlib.util.spec_from_loader("family_release", loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _index(listed: dict[str, list[str]]):
    def fetch(url: str) -> bytes | None:
        name = url.split("/pypi/")[1].split("/")[0]
        if name not in listed:
            return None                                   # a name the index does not know
        return json.dumps({"releases": {v: [] for v in listed[name]}}).encode()
    return fetch


def test_a_version_any_of_the_three_names_holds_is_named():
    release = _release()
    fetch = _index({"cs-image-system-gcloud-runtime-plugin": ["0.1.10", "0.2.0"],
                    "cs-image-system-tf-gcp-plugin": ["0.1.10"]})
    assert release.held("0.2.0", "pypi", fetch) == ["cs-image-system-gcloud-runtime-plugin"]
    assert release.held("0.1.10", "pypi", fetch) == ["cs-image-system-gcloud-runtime-plugin",
                                                     "cs-image-system-tf-gcp-plugin"]


def test_a_version_none_holds_is_free():
    release = _release()
    assert release.held("0.2.1", "test", _index({"cs-image-system-gcs-state-plugin": ["0.2.0"]})) == []


def test_an_index_that_cannot_be_asked_refuses_rather_than_guess():
    release = _release()

    def down(url: str) -> bytes | None:
        raise release.Refused("the index could not be asked")
    with pytest.raises(release.Refused):
        release.held("0.2.1", "pypi", down)
