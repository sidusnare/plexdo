<!--
SPDX-FileCopyrightText: 2026 SidusNare
SPDX-License-Identifier: GPL-3.0-or-later
SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
-->

# Contributing

## Getting set up

```bash
git clone https://github.com/sidusnare/plexdo.git
cd plexdo
make develop      # editable install with the dev extras, ruff included
npm ci            # markdownlint-cli2, at the version package.json pins
```

markdownlint-cli2 needs Node 22 or newer, and `.nvmrc` names the version CI
uses. Where the system's Node is older, as Debian stable's is, use the
official build from <https://nodejs.org/>, checking its `SHASUMS256.txt`
signature, and put its `bin` directory first on `PATH` for `npm ci` and
`make check`.

`make check` also needs ShellCheck, yamllint, and reuse; on Debian and Ubuntu
they come from `sudo apt install shellcheck yamllint reuse`.

## Before opening a pull request

```bash
make check
```

That runs, in order:

| step | what it enforces |
| --- | --- |
| `check-version` | the man page's version and the SBOM match `pyproject.toml`, the one place the version is defined |
| `check-assets` | packaged completions and man page match their sources; all source is ASCII |
| `smoke` | the package imports, the parser builds, every command module is registered |
| `test` | the test suite |
| `lint` | ruff check and ruff format, pylint at 10.00/10, ShellCheck, yamllint, markdownlint-cli2, and `reuse lint` |
| `build` + `dist-check` | the sdist and wheel build and pass `twine check` |

## House rules

- Google Python style: every function is annotated, `ruff format` decides the
  layout, and pylint must stay at 10.00/10. A linter suppression covers one
  line and one rule, with a comment saying why the code cannot change.
- Every file carries its SPDX copyright, licence, and, if written with AI,
  `SPDX-FileContributor` header, so `reuse lint` passes.
- A leading underscore means module-private. If another module imports it, it
  is package API and must not have one.
- Source files are plain ASCII. Write `-`, not an em dash. The box-drawing
  characters in `console.py` are `\uXXXX` escapes for this reason.
- Adding a command means adding a module under `src/plexdo/commands/` that
  exposes `register(sub, parents)`, `COMMANDS`, and `REQUIRES_PLEX`, then
  listing it in `MODULES`. `cli.py` should not need changing.
- Record every change for users under `## [Unreleased]` in `CHANGELOG.md`,
  and say which version component it will need: MAJOR for anything
  incompatible, MINOR for an addition, PATCH for a fix. Mark an incompatible
  entry **Breaking:**.

## Releasing

1. Set `version` in `pyproject.toml`, bumped by the component the Unreleased
   entries call for, under Semantic Versioning.
2. Move the Unreleased entries under `## [X.Y.Z] - YYYY-MM-DD`, and add the
   heading's comparison link.
3. `make derive`, which writes the version and date into the man page and
   regenerates `sbom.spdx.json`, then `make check`.
4. Tag and publish a GitHub release as `vX.Y.Z`. The workflow triggers on the
   release being published, not on the tag being pushed, so pushing a tag
   alone does nothing.

Set git to sort tags by version once per clone:

```bash
git config tag.sort version:refname
```

Without it `git tag` sorts lexically, so `v1.1.16` lands before `v1.1.6` and
the newest tag is not the last one listed. That only gets worse as the
revision passes 9.

Publishing to PyPI is automatic from `.github/workflows/publish.yml`, through
[Trusted Publishing](https://docs.pypi.org/trusted-publishers/), so no API
token is stored anywhere. The workflow reruns `make check`, refuses to publish
if the tag does not match the packaged version, and uploads from a `pypi`
environment you can put a protection rule on.

To rehearse against TestPyPI, run the workflow manually from the Actions tab
and choose `testpypi`.

Every workflow needs a `permissions:` block. `contents: read` at the top of
the file covers building and testing; a job needing more raises it for itself.
Omitting it hands jobs the repository default token and CodeQL reports it once
per job.

Actions are pinned to a major version and should be kept on the newest one.
GitHub retires the Node runtime under them every couple of years, so an
action left on an old major starts warning and eventually stops running;
`actions/checkout@v7`, `setup-python@v7`, `upload-artifact@v7`, and
`download-artifact@v8` are all on node24.

## The wiki

`.github/workflows/wiki.yml` publishes every `man/*.scd` page to the project
wiki whenever one changes on `main`: `man/plexdo-wait.1.scd` becomes the
wiki page `plexdo-wait`. Pull requests touching the pages build them without
publishing, so a page that does not compile, or links to one that does not
exist, fails there first. `make wiki` does the same build locally, given
scdoc and pandoc.

It needs setting up once: enable the wiki under Settings > Features > Wikis
and create its first page by hand, since GitHub only creates the wiki's
repository then. Until then the publish job fails saying exactly that.

Change the pages in `man/`, never on the wiki: a generated page is
overwritten on the next run. Each starts with a hidden `Generated from`
comment, and a page carrying it whose source has been removed is deleted.
Pages written on the wiki by hand never carry it, so they are left alone,
unless one is given the same name as a generated page. Run the workflow
from the Actions tab to resync everything after editing the wiki by hand.

`AI.prompt.md` is the authoritative specification. When behaviour changes,
update it in the same commit.
