# Contributing

## Getting set up

```bash
git clone https://github.com/sidusnare/plexdo.git
cd plexdo
make develop      # editable install with the dev extras
```

## Before opening a pull request

```bash
make check
```

That runs, in order:

| step | what it enforces |
| --- | --- |
| `check-version` | the version agrees across `__init__.py`, `pyproject.toml`, and the man page |
| `check-assets` | packaged completions and man page match their sources; all source is ASCII |
| `smoke` | the package imports, the parser builds, every command module is registered |
| `test` | the test suite |
| `lint` | pylint scores 10.00/10 |
| `build` + `dist-check` | the sdist and wheel build and pass `twine check` |

## House rules

- Every function is annotated, and pylint must stay at 10.00/10.
- A leading underscore means module-private. If another module imports it, it
  is package API and must not have one.
- Source files are plain ASCII. Write `-`, not an em dash. The box-drawing
  characters in `console.py` are `\uXXXX` escapes for this reason.
- Adding a command means adding a module under `src/plexdo/commands/` that
  exposes `register(sub, parents)`, `COMMANDS`, and `REQUIRES_PLEX`, then
  listing it in `MODULES`. `cli.py` should not need changing.
- Bump the revision (the third version field) for each release, in all three
  places `check-version` inspects.

## Releasing

1. Bump the revision in `src/plexdo/__init__.py`, `pyproject.toml`, and the
   `.TH` line of `man/plexdo.1`; `make check-version` verifies all three.
2. Add a `CHANGELOG.md` entry.
3. `make check`.
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
