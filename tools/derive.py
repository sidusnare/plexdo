#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Write the files derived from pyproject.toml, or check they are current.

pyproject.toml is the one place the version is defined. From it, and from
CHANGELOG.md for the release date, this writes:

  man/plexdo.1 and its packaged copy: the version and date on the .TH line;
  sbom.spdx.json: the SPDX 3.0 software bill of materials.

Usage: tools/derive.py [--check]

With --check nothing is written; the files that are out of date are named
and the exit status is 1.
"""

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAN_PAGES = (ROOT / "man/plexdo.1", ROOT / "src/plexdo/data/plexdo.1")
SBOM = ROOT / "sbom.spdx.json"

# The AI model that generated the code, as far as is recorded; models used
# in earlier sessions were not recorded and cannot be named.
AI_MODEL = "Claude Opus 5.5"


def semver(version: str) -> str:
    """The SemVer spelling of a PEP 440 version, as tags and CHANGELOG.md use.

    pyproject.toml must spell a pre-release the PEP 440 way, 2.0.0rc1, which
    SemVer writes 2.0.0-rc.1.
    """
    names = {"a": "alpha", "b": "beta", "rc": "rc"}
    match = re.fullmatch(r"(\d+\.\d+\.\d+)(a|b|rc)(\d+)", version)
    if not match:
        return version
    release, kind, number = match.groups()
    return f"{release}-{names[kind]}.{number}"


def release_date(version: str) -> str | None:
    """The date CHANGELOG.md gives the release of version, if any."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    found = re.search(
        rf"^## \[{re.escape(semver(version))}\] - (\d{{4}}-\d{{2}}-\d{{2}})$",
        changelog,
        re.M,
    )
    return found.group(1) if found else None


def stamped_man_page(text: str, version: str, date: str | None) -> str:
    """The man page with the version, and release date, on its .TH line.

    An unreleased version keeps the date already there.
    """
    match = re.search(r'^\.TH PLEXDO 1 "([^"]*)" "plexdo [^"]*"', text, re.M)
    if not match:
        sys.exit("No .TH PLEXDO 1 line in the man page.")
    line = f'.TH PLEXDO 1 "{date or match.group(1)}" "plexdo {version}"'
    return text[: match.start()] + line + text[match.end() :]


def _ids(base: str):
    """A function making the SPDX ids of this document's elements."""

    def spdx_id(name: str) -> str:
        return f"{base}#{name}"

    return spdx_id


def _requirement_name(requirement: str) -> str:
    """The distribution name of a requirement such as "PyYAML>=6.0"."""
    return re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0]


def sbom(project: dict, date: str | None, npm: dict) -> dict:
    """The SPDX 3.0.1 SBOM for this version, as JSON-LD.

    Only what is declared is recorded. The versions each dependency is
    installed at are resolved at install time, and the dependencies of
    dependencies are not listed, so both are left for an SBOM tool run
    against an installation to fill in; no checksum is given.
    """
    meta = project["project"]
    name, version = meta["name"], meta["version"]
    spdx_id = _ids(f"https://github.com/sidusnare/plexdo/spdx/{version}")
    info = "_:creationinfo"
    author = meta["authors"][0]["name"]

    def element(kind: str, ident: str, **fields) -> dict:
        return {
            "type": kind,
            "spdxId": spdx_id(ident),
            "creationInfo": info,
            **fields,
        }

    graph = [
        {
            "type": "CreationInfo",
            "@id": info,
            "specVersion": "3.0.1",
            "created": f"{date or '1970-01-01'}T00:00:00Z",
            "createdBy": [spdx_id("author")],
            "createdUsing": [spdx_id("ai-model"), spdx_id("derive")],
            "comment": (
                "The code was generated with the AI model named in "
                "createdUsing; models used before it was recorded are not "
                "known. plexdo neither includes nor depends on an AI model, "
                "so the SPDX AI profile does not apply."
            ),
        },
        element("Person", "author", name=author),
        element(
            "Tool",
            "ai-model",
            name=AI_MODEL,
            comment="The AI model that generated the code (AI-generated).",
        ),
        element("Tool", "derive", name="tools/derive.py"),
        element(
            "simplelicensing_LicenseExpression",
            "license",
            simplelicensing_licenseExpression=meta["license"],
        ),
        element(
            "simplelicensing_LicenseExpression",
            "data-license",
            simplelicensing_licenseExpression="CC0-1.0",
        ),
        element(
            "software_Package",
            "package",
            name=name,
            software_packageVersion=version,
            software_packageUrl=f"pkg:pypi/{name}@{version}",
            software_downloadLocation=meta["urls"]["Source"],
            software_homePage=meta["urls"]["Homepage"],
            software_primaryPurpose="application",
            suppliedBy=spdx_id("author"),
            originatedBy=[spdx_id("author")],
            description=meta["description"],
        ),
    ]
    scopes = {
        "runtime": meta["dependencies"],
        "build": project["build-system"]["requires"],
        "development": meta["optional-dependencies"]["dev"],
    }
    for scope, requirements in scopes.items():
        targets = []
        for requirement in requirements:
            dist = _requirement_name(requirement)
            ident = f"pypi-{dist.lower()}"
            if not any(e.get("spdxId") == spdx_id(ident) for e in graph):
                graph.append(
                    element(
                        "software_Package",
                        ident,
                        name=dist,
                        software_packageUrl=f"pkg:pypi/{dist.lower()}",
                        comment=f"Declared in pyproject.toml as {requirement}.",
                    )
                )
            targets.append(spdx_id(ident))
        if scope == "development":
            for dist, spec in sorted(npm.get("devDependencies", {}).items()):
                ident = f"npm-{dist}"
                graph.append(
                    element(
                        "software_Package",
                        ident,
                        name=dist,
                        software_packageUrl=f"pkg:npm/{dist}",
                        comment=f"Declared in package.json as {dist}@{spec}.",
                    )
                )
                targets.append(spdx_id(ident))
        graph.append(
            element(
                "LifecycleScopedRelationship",
                f"depends-{scope}",
                relationshipType="dependsOn",
                scope=scope,
                to=targets,
                **{"from": spdx_id("package")},
            )
        )
    graph.append(
        element(
            "Relationship",
            "declared-license",
            relationshipType="hasDeclaredLicense",
            to=[spdx_id("license")],
            **{"from": spdx_id("package")},
        )
    )
    elements = [e["spdxId"] for e in graph if "spdxId" in e]
    graph.append(
        element(
            "SpdxDocument",
            "document",
            name=f"{name} {version}",
            dataLicense=spdx_id("data-license"),
            profileConformance=["core", "software", "simpleLicensing"],
            rootElement=[spdx_id("package")],
            element=elements,
        )
    )
    return {
        "@context": "https://spdx.org/rdf/3.0.1/spdx-context.jsonld",
        "@graph": graph,
    }


def main(argv: list[str]) -> int:
    """Write the derived files, or with --check report any out of date."""
    check = "--check" in argv
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    version = project["project"]["version"]
    date = release_date(version)
    npm_path = ROOT / "package.json"
    npm = json.loads(npm_path.read_text("utf-8")) if npm_path.exists() else {}

    wanted = {
        page: stamped_man_page(page.read_text("utf-8"), version, date)
        for page in MAN_PAGES
    }
    wanted[SBOM] = json.dumps(sbom(project, date, npm), indent=2) + "\n"

    stale = [
        path
        for path, text in wanted.items()
        if not path.exists() or path.read_text("utf-8") != text
    ]
    if check:
        for path in stale:
            print(
                f"out of date: {path.relative_to(ROOT)} (run make derive)",
                file=sys.stderr,
            )
        if not stale:
            print(f"derived files match version {version} in pyproject.toml")
        return 1 if stale else 0
    for path in stale:
        path.write_text(wanted[path], encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
