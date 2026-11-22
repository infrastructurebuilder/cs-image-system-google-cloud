# SPDX-FileCopyrightText: 2026 Mykel Alvis <mykelalvis@infrastructurebuilder.org>
#
# SPDX-License-Identifier: Apache-2.0

# The Google Cloud provider family's lifecycle: init, build, test, full-test,
# release. Everything of the system it needs comes from the package index by
# range (pyproject.toml); nothing here reads another repository's checkout.

set shell := ["bash", "-uc"]

packages := "gcloud-runtime-plugin tf-gcp-plugin gcs-state-plugin"

default:
	@just --list

# One-time setup, idempotent: the environment exactly as the lock has it, from the index
init:
	uv sync --locked --all-extras

# The three wheels and their sdists, in dist/
build:
	uv build --all-packages

# The local acceptance tests: lint, the type check (zero errors), each package's
# surface self-check, and every unit and pipeline test with the golden, under the
# test kit's strict session (a run that collects nothing or skips anything fails)
test: lint typecheck surface-check pytest

# `test`, then the legs that need more than the process: the low end of the SDK
# ranges, and the two starters that declare Google Cloud rendered, validated and
# dry-run with the system from the index (scripts/full-test-legs says each leg)
full-test: test
	uv run --no-sync python scripts/full-test-legs

# Cut a release of the family: PART is a bump-my-version part (major, minor,
# patch) or an explicit version; INDEX is `test` (TestPyPI) or `pypi`, the index an
# upload token in the environment uploads to (none needed: see below). It refuses a
# version either index ever held, moves the one number in the three manifests, runs
# `full-test`, builds, then commits and tags v<version>. Pushing the tag publishes the
# three (the Publish workflow, by trusted publishing: docs/RELEASING.md). `yes` as the
# third argument is the dry form: the plan, nothing changed.
release part index="test" dry="no": init
	uv run --no-sync python scripts/release "{{part}}" "{{index}}" "{{dry}}"

# Ruff (blocking), then the licensing check (an SPDX header or a REUSE.toml declaration on every file)
lint:
	uv run --no-sync ruff check packages tests scripts
	uv run --no-sync reuse lint

# Sort imports and apply ruff's safe fixes; review the diff
lint-fix:
	uv run --no-sync ruff check --fix packages tests scripts

# Pyright in standard mode over the workspace; zero errors
typecheck:
	uv run --no-sync pyright

# Each package's sources keep to the SDK's declared surfaces (the kit's own check, as a plugin
# author runs it); each package's tests/test_keeps_to_the_surface.py holds its sources and its
# tests to the same, inside `pytest`
surface-check:
	#!/usr/bin/env bash
	set -euo pipefail
	for p in {{packages}}; do
	  uv run --no-sync python -m cs_image_system.base.surface check "packages/$p/src"
	done

# The tests alone (`test` runs them after lint, the type check and the surface check)
pytest *ARGS:
	uv run --no-sync pytest {{ARGS}}

# Rewrite the golden from a stubbed run of the fixture, on purpose, after an intended
# change to the emission; then read every rewritten file
golden-regen:
	uv run --no-sync python tests/regen_golden.py

# The tests that need a Google Cloud session (tests/live): never part of `test` or
# `full-test`; they fail, never skip, without a session; whatever they stand up they tear down
test-live:
	uv run --no-sync pytest tests/live -p cs_image_system.system.testing.strict

# Nothing in the tree must be unsafe for the open internet (the system's own scanner)
public-safe *ARGS:
	uv run --no-sync cs-image-system public-safe --tree . --config tests/fixture/cfg/_config.yml {{ARGS}}
