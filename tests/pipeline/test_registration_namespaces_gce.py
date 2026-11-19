# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

"""The ``tf-gcp`` namespace: the family's Terraform-root plugin carries the
OpenTofu version checker, so a tree whose roots are all Google Cloud's still
has its tool checked; registered under ``tf-gcp`` it is one registration,
resolved by the bare word ``tofu`` and by ``tf-gcp/tofu``; installed, the
plugin's instance-builder word resolves bare and qualified to one class;
and a ``tf-gcp/...`` word keeps its namespace where a bare one stays bare.

Carried from cs-image-system-3's ``tests/test_registration_namespaces.py``
(spec 005, T024). There the checker case loads three root plugins
(``tf-ebs-instance``, ``tf-gcp``, ``tf-docker``) to prove the same class
under three namespaces is one registration; only ``tf-gcp`` is installed
here, so its half is carried. The namespace derivation, the ambiguity
rules and the discovery refusals are the core's and stay there.
"""
from __future__ import annotations

from cs_image_system.base.registry import RegistrationKey, Registry
from cs_image_system.contract.constants import VCT
from cs_image_system.contract.core import PluginMetadataProtocol

WORD = "tofu"
NAMESPACE = "tf-gcp"


def _load(reg: Registry, md: PluginMetadataProtocol, namespace: str) -> None:
    """What the loader does for one plugin's metadata."""
    reg.register_plugin_metadata(md, namespace=namespace)
    for services in md.services.values():
        for service in services:
            reg.register_service(service, namespace=namespace)


def test_the_tf_gcp_root_carries_the_tofu_checker_as_one_registration():
    from cs_image_system.tf_gcp_plugin.main import initialize
    from cs_image_system.tofu_roots.tofu_instance_builder import TofuVersionChecker
    reg = Registry()
    _load(reg, initialize(), NAMESPACE)
    keys = [k for k in reg.registration_keys(VCT.VERSION_CHECKER) if k.name == WORD]
    assert [k.namespace for k in keys] == [NAMESPACE]
    assert reg.get_model(VCT.VERSION_CHECKER, WORD) is TofuVersionChecker
    assert reg.get_builder_for_model(WORD, VCT.VERSION_CHECKER) is TofuVersionChecker
    assert reg.get_model(VCT.VERSION_CHECKER, f"{NAMESPACE}/{WORD}") is TofuVersionChecker
    assert reg.models_under(VCT.VERSION_CHECKER)[WORD] is TofuVersionChecker
    assert reg.vct_type_registry[VCT.VERSION_CHECKER].count(TofuVersionChecker) == 1
    assert [k.namespace for k in reg.reverse_registry[TofuVersionChecker]] == [NAMESPACE]


def test_the_installed_tf_gcp_root_resolves_by_the_bare_word_and_its_qualified_form():
    from cs_image_system.engine.loader import installed_registry
    from cs_image_system.tofu_roots.tofu_instance_builder import TofuVersionChecker
    reg = installed_registry()
    assert reg.get_model(VCT.VERSION_CHECKER, WORD) is TofuVersionChecker
    assert reg.get_model(VCT.VERSION_CHECKER, f"{NAMESPACE}/{WORD}") is TofuVersionChecker
    # the installed instance-builder word is the family root's alone, so bare and qualified agree
    gce_root = reg.get_model(VCT.INSTANCE_BUILDER_MODEL, "tofu-gce")
    assert gce_root is not None and reg.get_model(VCT.INSTANCE_BUILDER_MODEL, f"{NAMESPACE}/tofu-gce") is gce_root


def test_a_bare_word_stays_bare_and_a_qualified_word_keeps_its_namespace():
    """The orchestrator canonicalises an alias but never rewrites a bare
    word to its qualified form (the mod fingerprint hashes the type word)
    nor a qualified one to the bare word."""
    from cs_image_system.base.registry import bare_name, split_qualified
    assert split_qualified(WORD) == (None, WORD)
    assert split_qualified(f"{NAMESPACE}/{WORD}") == (NAMESPACE, WORD)
    assert bare_name(f"{NAMESPACE}/{WORD}") == WORD == bare_name(WORD)
    assert RegistrationKey(VCT.VERSION_CHECKER, NAMESPACE, WORD).qualified == f"{NAMESPACE}/{WORD}"
