# cs-image-system-google-cloud

The Google Cloud provider family for
[cs-image-system](https://github.com/infrastructurebuilder/cs-image-system-3):
the plugins that make Google Compute Engine a place where images are baked
and instances run, the OpenTofu roots for its instances and storages, and
a Google Cloud Storage state backend. The family moved here, with its
history, from the system's repository, and releases on its own version
line.

## The family

Three distributions, released together under one number:

| Distribution | Import package | Provides | Entry points |
| --- | --- | --- | --- |
| [`cs-image-system-gcloud-runtime-plugin`](packages/gcloud-runtime-plugin/README.md) | `cs_image_system.gcloud_runtime` | the `gcloud` runtime type: vendor images resolved by project and family, the `googlecompute` packer source, IAP sessions, the state query and the instance hooks on GCE; the GCP section of the bootstrap; the GCP terraform modules, as package data | `cs_image_system.plugins.runtime`: `gcloud`; `cs_image_system.bootstrap`: `gcp`; `cs_image_system.modules`: `modules` |
| [`cs-image-system-tf-gcp-plugin`](packages/tf-gcp-plugin/README.md) | `cs_image_system.tf_gcp_plugin` | the OpenTofu builders: the `tofu-gce` instance builder and the `tf-gcp-pd`, `tf-gcp-filestore` and `tf-gcp-gcs` storage builders | `cs_image_system.plugins.instance`: `tf-gcp-plugin` |
| [`cs-image-system-gcs-state-plugin`](packages/gcs-state-plugin/README.md) | `cs_image_system.gcs_state_plugin` | the `gcs` state backend | `cs_image_system.plugins.state`: `gcs_state_plugin` |

The Terraform plugin depends on the runtime at the family's exact number;
each package depends on the parts of the system's SDK it uses (the
contract, the kit, the Terraform libraries) by range.

## Installing

An operator installs the family through the system's own `gcloud` extra:

```sh
uv tool install 'cs-image-system[gcloud]'
```

The extra installs the family's three distributions by a range on their
releases. The system's operations guide states the install once, with
every provider's extra:
[OPERATIONS.md, "Installing a release"](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/OPERATIONS.md#installing-a-release).

## Building and testing

The [`Justfile`](Justfile) is the one entry point; `just --list` names
every target.

```sh
just init         # once, idempotent: the environment exactly as uv.lock has it
just test         # lint, the type check, each package's surface check, the unit and pipeline tests and the golden
just full-test    # `test`, then the low end of the SDK ranges and the Google Cloud starters rendered, validated and dry-run
```

Everything of the system the family needs comes from the package index
by range: the SDK as the packages' dependencies, and the command line
with its test kit and the core plugins the fixture declares as the
workspace's `dev` group ([pyproject.toml](pyproject.toml)). Nothing here
reads another repository's checkout.

The tests run under the test kit's strict session: a run that collects
nothing or skips anything fails. The pipeline tests
([tests/pipeline](tests/pipeline)) drive stubbed runs over the family's
own fixture ([tests/fixture](tests/fixture)) and compare the emission
with its golden ([tests/golden](tests/golden)). After an intended change
to the emission, `just golden-regen` rewrites the golden; read every
rewritten file before committing it.

`just test-live` runs the tests that need a Google Cloud session. It is
never part of `test` or `full-test`; without a session its tests fail
rather than skip, and whatever they stand up in the project they tear
down.

## Releasing

```sh
just release <part> pypi            # full-test, then a commit and the tag v<version>
git push origin HEAD v<version>     # the tag's push publishes the three
```

`<part>` is `major`, `minor`, `patch` or an explicit version. The release
moves the family's one number in the three manifests, refuses a version
either index ever held for any of them, runs `full-test`, builds, then
commits and tags `v<version>`. `yes` as a third argument is the dry form:
the plan, with nothing changed.

Pushing the tag publishes the release: the `Publish` workflow uploads the
three to TestPyPI and then, for a final version, PyPI, by trusted
publishing, so no upload token is stored anywhere.
[docs/RELEASING.md](docs/RELEASING.md) says how that trust is set up on
each index and in the repository, and what a fork must change to publish
under names of its own.

## Documents

- [docs/CONFIGURATION.md](docs/CONFIGURATION.md): the fields of the
  `gcloud` runtime and the `gcs` state backend, the one source for them.
- [docs/RELEASING.md](docs/RELEASING.md): how a release is cut and
  published, setting up trusted publishing, and releasing a fork.
- The package READMEs, linked in the table above: each package in depth,
  from what it registers to how it fails.
- The system's documents for everything else: the
  [operations guide](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/OPERATIONS.md),
  the rest of the
  [configuration reference](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md),
  and how a provider depends on the SDK
  ([WRITING_A_PROVIDER.md](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/WRITING_A_PROVIDER.md#how-it-depends-on-the-sdk)).

## Licence

Apache-2.0 ([LICENSE](LICENSE)). Every file carries an SPDX header or is
declared in [REUSE.toml](REUSE.toml); `just lint` runs `reuse lint`.
