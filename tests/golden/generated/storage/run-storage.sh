#!/usr/bin/env bash
# cs-image-system lifecycle runner: storage
# run id: 2026_08_26t12_00_00
# Deferred commands accumulated while generating this lifecycle,
# in phase order. Paths are relative to this lifecycle's directory.
# state: workspace gcp-gcs -> gcs://csis-sandbox-tfstate/statefiles/csia/gcp_gcs/default.tfstate
# state: workspace gcp-pd -> gcs://csis-sandbox-tfstate/statefiles/csia/gcp_pd/default.tfstate
# NOTE: builders' pre/post finalize hooks are NOT part of this
# script; a --no-dry-run run performs them in-process.
set -euo pipefail
cd "$(dirname "$0")"
CSIS_ROOT="$(cd "../.." && pwd)"   # the configuration root, relative to this script

# --- phase: storage-generation ---
( cd "gcp-gcs/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && rm -f tfplan )
( cd "gcp-gcs/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && /usr/local/bin/tofu init -input=false -reconfigure -backend-config=gcp-gcs-storage-generation.tfbackend.hcl )
( cd "gcp-gcs/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && /usr/local/bin/tofu plan -input=false -out=tfplan )
( cd "gcp-gcs/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && cs-image-system gate-plan --planfile tfplan --tofu /usr/local/bin/tofu )
( cd "gcp-pd/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && rm -f tfplan )
( cd "gcp-pd/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && /usr/local/bin/tofu init -input=false -reconfigure -backend-config=gcp-pd-storage-generation.tfbackend.hcl )
( cd "gcp-pd/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && /usr/local/bin/tofu plan -input=false -out=tfplan )
( cd "gcp-pd/storage-generation" && cd "$(cs-image-system materialize . --root-dir "$CSIS_ROOT")" && cs-image-system gate-plan --planfile tfplan --tofu /usr/local/bin/tofu )
