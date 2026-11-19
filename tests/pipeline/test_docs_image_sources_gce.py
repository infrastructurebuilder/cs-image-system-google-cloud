# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The gcloud runtime documents its own translation: its README carries an
"Image query translation" table, one row per key of the system's
vocabulary, saying exactly what ``supported_query_keys()`` says, and names
the part of the image-source catalog the plugin ships
(``data/image-sources.yml``).

Carried from cs-image-system-3's ``tests/test_docs_image_sources.py``
(spec 005, T024): the ``gcloud-runtime-plugin`` parametrization of its two
README cases. The other runtimes' READMEs and the contract's vocabulary
list stay there.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

from family import REPO

from cs_image_system.contract.image import QUERY_KEYS
from cs_image_system.gcloud_runtime.gcp_runtime_builders import GCPCloudBuilder

PACKAGE = REPO / "packages" / "gcloud-runtime-plugin"
HEADING = "### Image query translation"
ROW = re.compile(r"^\|\s*`([a-z_]+)`\s*\|\s*([^|]*?)\s*\|")


def _table(readme: Path) -> dict[str, str]:
    text = readme.read_text()
    assert HEADING in text, f"{readme.relative_to(REPO)} has no '{HEADING}' section"
    section = text.split(HEADING, 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        m = ROW.match(line)
        if m and m.group(1) != "key":
            rows[m.group(1)] = m.group(2)
    return rows


def test_the_translation_table_says_what_the_plugin_declares():
    rows = _table(PACKAGE / "README.md")
    missing = [k for k in QUERY_KEYS if k not in rows]
    assert not missing, f"the table lacks a row for {missing}"
    documented = {k for k, native in rows.items() if native.lower() != "refused"}
    declared = GCPCloudBuilder.supported_query_keys(cast(Any, None))      # the hook reads nothing of self
    assert documented == declared, (f"the README says {sorted(documented)} are translated, "
                                    f"the plugin says {sorted(declared)}")


def test_the_readme_names_the_catalog_part_the_plugin_ships():
    text = (PACKAGE / "README.md").read_text()
    data = PACKAGE / "src" / "cs_image_system" / "gcloud_runtime" / "data" / "image-sources.yml"
    assert data.is_file()
    assert "data/image-sources.yml" in text, f"the README does not name {data.relative_to(REPO)}"
    assert GCPCloudBuilder.image_source_entries(), "the plugin ships no catalog entries"
