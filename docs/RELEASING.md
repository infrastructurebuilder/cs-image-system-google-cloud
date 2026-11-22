# Releasing the Google Cloud family

A release of the family's three distributions, under its one number, takes
two commands and no secret:

```sh
just release <part|version> pypi    # full-test, then a commit and the tag v<version>
git push origin HEAD v<version>     # the tag's push publishes the three
```

The first runs on the operator's machine. It checks that the version is new
on both indexes for all three, runs `just full-test`, builds, commits if
anything changed, and tags. The second hands the tag to GitHub, and the
`Publish` workflow
([.github/workflows/publish.yml](../.github/workflows/publish.yml)) uploads
the three builds to TestPyPI and then, for a final version, to PyPI.

No upload token is involved. The workflow uses **trusted publishing**: each
index has been told to accept uploads for each of the three projects from
one GitHub repository, one workflow file and one GitHub environment. The
workflow proves it is that workflow with a short-lived token GitHub issues
to the job, so there is no long-lived token to store, leak or rotate. This
page says how that trust is set up, so it can be set up again: by a new
maintainer, after a repository move, or by someone who forks this
repository.

`just release 0.2.1 pypi yes` is the dry form: it says what it would do and
changes nothing.

## How the release decides where to upload

- **No token in the environment (the usual case):** the script uploads
  nothing. It tags, and the tag's push publishes.
- **A token in the environment** (`UV_PUBLISH_TOKEN`, or `PYPI_TOKEN` /
  `TEST_PYPI_TOKEN` for the index named): the script uploads to the index
  named itself, before tagging. The workflow still runs on the tag's push,
  finds those files already on the index and skips them (`uv publish
  --index` checks the index it publishes to), and uploads only what is
  missing.

Either way, a version either index has ever listed for any of the three is
refused before anything changes. An index never takes a second build under
a version it held, even a deleted one, so a version is never cut twice.

## Setting up trusted publishing

This is done once per project and per index, by someone who is an
**Owner** of the projects on that index. It needs no change to the
repository: the workflow is already written for it.

**Names, not to be mixed up.** The projects on each index are named after
the packages: **`cs-image-system-gcloud-runtime-plugin`**,
**`cs-image-system-tf-gcp-plugin`** and **`cs-image-system-gcs-state-plugin`**
(each at `https://pypi.org/project/<name>/` and
`https://test.pypi.org/project/<name>/`). The repository on GitHub is
**`cs-image-system-google-cloud`**. There is no index project called
`cs-image-system-google-cloud`. Each project is where a publisher is added;
the repository's name is what the publisher form asks for.

| Name | What it is | Where it is used below |
| --- | --- | --- |
| `cs-image-system-gcloud-runtime-plugin`, `cs-image-system-tf-gcp-plugin`, `cs-image-system-gcs-state-plugin` | the three projects on PyPI and TestPyPI (`[project] name` in each `packages/*/pyproject.toml`) | the projects you open to add a publisher, one each |
| `cs-image-system-google-cloud` | the GitHub repository, under the owner `infrastructurebuilder` | the form's **Repository name** field |

If one of the three is not under **Your projects**, the account signed in
is not one of its owners; its publisher is added from an account that is.

### 1. On PyPI

1. Sign in to [pypi.org](https://pypi.org) as an Owner of the three
   projects.
2. Open **Your projects**, find `cs-image-system-gcloud-runtime-plugin`
   (not `cs-image-system-google-cloud`, which is the repository), and
   choose **Manage**.
3. Choose **Publishing** in the project's menu.
4. Under **Add a new publisher**, choose the **GitHub** tab and fill in:

   | Field | Value |
   | --- | --- |
   | Owner | `infrastructurebuilder` |
   | Repository name | `cs-image-system-google-cloud` (the GitHub repository, not a project) |
   | Workflow name | `publish.yml` |
   | Environment name | `pypi` |

5. Choose **Add**. The publisher is listed under the project's publishers.
6. Do steps 2 to 5 again for `cs-image-system-tf-gcp-plugin` and for
   `cs-image-system-gcs-state-plugin`, with the same four values. Each
   project needs its own publisher: an upload for a project without one is
   refused.

### 2. On TestPyPI

TestPyPI is a separate site with its own accounts and its own trust. Do the
same at [test.pypi.org](https://test.pypi.org), for the same three
projects, with one difference:

| Field | Value |
| --- | --- |
| Environment name | `testpypi` |

The owner, repository name and workflow name are the same as for PyPI.

### 3. On GitHub

The environment names above must exist in the repository, because the index
checks the environment the job ran in.

1. In the repository on GitHub, open **Settings**, then **Environments**.
2. Choose **New environment**, name it `testpypi`, and choose **Configure
   environment**.
3. Do the same for `pypi`.
4. Optional, and recommended for `pypi`:
   - **Required reviewers**: name yourself, so every PyPI upload waits for
     your approval in the workflow run, after TestPyPI has taken it.
   - **Deployment branches and tags**: choose **Selected branches and tags**
     and add the tag rule `v*`, so only a release tag can use the
     environment.

Neither environment needs a secret.

### 4. Check it

Push a tag for a version that is new on both indexes, then watch the run:

```sh
GH_PAGER=cat gh run list --repo infrastructurebuilder/cs-image-system-google-cloud --workflow publish.yml --limit 1
```

The `testpypi` job publishes first. The `pypi` job runs after it, and only
for a final version. A job that fails with `invalid-publisher` names the
claim the index did not recognise; compare it with the four fields above. A
repository, workflow file or environment that was renamed needs its
publisher entries changed to match.

## If you fork this repository

A fork can build and test everything as it is: CI needs no secret. It cannot
publish under these projects' names, which belong to the upstream projects'
owners on both indexes. The `Publish` workflow therefore runs only in the
upstream repository (the `if: github.repository == ...` line of its `build`
job), so a fork's tag push does nothing until the fork makes it its own.

To release a fork under names of its own:

1. **Choose three new distribution names** and write them in each
   `packages/*/pyproject.toml` (`[project] name`), in the Terraform plugin's
   exact pin on the runtime (`packages/tf-gcp-plugin/pyproject.toml`, and
   the `[[tool.bumpversion.files]]` entry for it in the root
   `pyproject.toml`), and in `NAMES` in [scripts/release](../scripts/release).
   - A name decides its package's **namespace**: the qualified form of its
     words. Today they are `gcloud-runtime`, `tf-gcp` and `gcs-state`, so a
     tree may write `gcloud-runtime/gcloud`. New names give new namespaces,
     and a tree that wrote the old qualified words must write the new ones
     (`tests/pipeline/test_qualified_words.py` names them). Bare words
     (`gcloud`) are unaffected.
   - The system's `gcloud` extra (`cs-image-system[gcloud]`) installs the
     upstream family by its names. A fork's family is installed by its own
     names instead, for example
     `uv tool install cs-image-system --with <runtime-name> --with <tf-name> --with <gcs-name>`.
2. **Point the workflow at the fork**: change the repository named in the
   `if:` line of `.github/workflows/publish.yml` to `<you>/<your-repo>`, and
   the package whose version the tag is checked against if you renamed its
   directory.
3. **Register a pending publisher on each index, for each project.** A
   project that does not exist yet is set up from your account rather than
   from a project: on pypi.org, open **Your account**, then **Publishing**,
   then **Add a new pending publisher**, once for each of the three. Fill in
   the new project name, your GitHub owner and repository, `publish.yml` and
   `pypi`. Do the same on test.pypi.org with `testpypi`. The first upload
   creates each project, with you as its owner, and turns its pending
   publisher into a normal one.
4. **Create the `testpypi` and `pypi` environments** in your repository, as
   in step 3 above.
5. **Release**: `just release <version> pypi`, then push the tag.

If you would rather upload with a token than set up trusted publishing,
export it as `UV_PUBLISH_TOKEN` (or `PYPI_TOKEN` / `TEST_PYPI_TOKEN`) when you
run `just release`. The script then uploads from your machine, and the
workflow, once pointed at your fork, only checks what is already there.
