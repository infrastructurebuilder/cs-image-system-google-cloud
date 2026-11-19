# Configuration reference: the Google Cloud family

This document is the reference for the configuration fields the Google
Cloud provider family defines: the `gcloud` runtime and the `gcs` state
backend. It is the one source for those fields. Everything else in a
configuration tree -- its files and load order, the fields every builder
and every runtime shares, networking, OS builders, images, instances,
storages, overlays and encrypted values -- is described in the system's
configuration reference,
[docs/CONFIGURATION.md](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md),
and a section number below (4.1, 4.5, 5.1.1, 10) is that document's.

The models are the source of truth:
[`gcp_runtime_models.py`](../packages/gcloud-runtime-plugin/src/cs_image_system/gcloud_runtime/gcp_runtime_models.py)
for the runtime and
[`gcs_state_models.py`](../packages/gcs-state-plugin/src/cs_image_system/gcs_state_plugin/gcs_state_models.py)
for the backend. The examples are the family's fixture, under
[`tests/fixture/`](../tests/fixture/). Each package's README gives the
longer account of what every field feeds, its variations and its
failures ([gcloud-runtime-plugin](../packages/gcloud-runtime-plugin/README.md),
[gcs-state-plugin](../packages/gcs-state-plugin/README.md)). The fields
of the family's OpenTofu builders (`tofu-gce`, `tf-gcp-pd`,
`tf-gcp-filestore`, `tf-gcp-gcs`) are rows of the system's shared tables
in [8.1](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#81-instance-builders)
and [8.2](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#82-storage-builders),
and the [tf-gcp-plugin README](../packages/tf-gcp-plugin/README.md#configuration-reference)
lists every one of them.

As in the system's reference, an unknown key is an error, `type` is the
YAML key (the Python field is `type_`), and "required" means the load
refuses an entry without it.

## The `gcloud` runtime

An entry of `runtime_builders:` in `cfg/runtime-builders.yml` with
`type: gcloud`: `GCPCloudBuilderModel`. The fields common to every
builder
([4.1](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#41-fields-common-to-every-builder))
and to every runtime
([4.2](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#42-fields-common-to-every-runtime))
apply as well.

| Field | Type | Default | Meaning and allowed values |
| --- | --- | --- | --- |
| `project_id` | str or null | null | the project |
| `zone` | str or null | null | the zone for build VMs and instances |
| `service_account_email` | str or null | null | the service account attached to build VMs (the packer source); the instance module attaches none |
| `default_disk_size` | int or null | null | bake disk size in GB for every image baked here (a GCE boot disk is exactly its image's disk); null uses the image's own value |
| `bake_preemptible` | bool | `false` | bake on preemptible (spot) build VMs |
| `state_configuration` | str | `default` | a state backend ([section 10](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#10-cfgstate-backendsyml)); `default` inherits the runtime's, else the default backend |
| `ssh_username` | str | `default` | the bake ssh user for every image on this runtime that names none more specifically: step 4 of the bake-user order ([5.1.1](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#511-the-bake-ssh-user)); with nothing named anywhere, GCE bakes as `packer` |
| `session_mechanism` | str or null | null | `iap` is the only supported value; with none declared, every session command (post-bake verify, unmount, the alias writer) is refused naming the field |
| `executable` | str or null | `gcloud` | the `cfg/executables.yml` entry every gcloud call on this runtime runs through (sessions, inventory, the GCP storage lookups and scripts); `validate` refuses it undeclared |
| `networking` | mapping or null | null | [4.5](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#45-networking) with `network_tags` |
| `credentials` | mapping | `{}` | the empty base: GCE uses Application Default Credentials, so any key here is refused |

At load the GCP runtime resolves the project; when it can, it checks
`networking.network` (or `default`) and every subnet against the project
and warns about a network tag no firewall rule targets.

The fixture's runtime is `gcloud-east1` in
[`tests/fixture/cfg/runtime-builders.yml`](../tests/fixture/cfg/runtime-builders.yml).

## The `gcs` state backend

An entry of `state_backends:` with `type: gcs`: `GcsStateBuilderModel`.
How a root's backend resolves, and where its state lives, is the
system's
[section 10](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#10-cfgstate-backendsyml).

A Google Cloud Storage bucket. The family's fixture declares one,
`gcs-east1`, as its default backend and binds its GCE roots to it; the
live tree keeps its GCE roots on the S3 backend by the standing decision,
and carries the same declaration with every line commented out.

| Field | Type | Default | Meaning and allowed values |
| --- | --- | --- | --- |
| common builder fields ([4.1](https://github.com/infrastructurebuilder/cs-image-system-3/blob/develop/docs/CONFIGURATION.md#41-fields-common-to-every-builder)) | | | `is_default` marks the backend `default` resolves to |
| `bucket` | str | required, non-empty | the state bucket |
| `prefix` | str | `statefiles` | the prefix inside the bucket; each root gets `<prefix>/<root name>` beneath it |
| `credentials` | str or null | null | a PATH to a credentials file, never a value |
| `impersonate_service_account` | str or null | null | the service account terraform impersonates |
| `encryption_key` | str or null | null | a customer-supplied key |
| `kms_encryption_key` | str or null | null | a Cloud KMS key name |
| `executable` | str or null | null | the `cfg/executables.yml` entry these roots run; when declared `validate` refuses a name that is not in the list, and the entry is version-checked like any other; unset, nothing is checked |

A root's location is `gcs://<bucket>/<prefix>/<root name>/default.tfstate`
(OpenTofu's `gcs` backend names the default terraform workspace's object
`default.tfstate` under the prefix, so each root gets its own prefix). The
backend file carries `bucket`, `prefix`, the identity fields and the
encryption keys when set; a consumer's data source `bucket`, `prefix` and
the identity fields only. `required_plugins` is refused at load (a
backend has no plugins).

[`tests/fixture/cfg/state-backends.yml`](../tests/fixture/cfg/state-backends.yml),
its `gcs` entry:

```yaml
---
state_backends:
- name: gcs-east1
  type: gcs
  bucket: csis-sandbox-tfstate
  prefix: statefiles/csia
  is_default: true
```
