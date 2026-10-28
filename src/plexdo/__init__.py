# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
#
# plexdo - a command-line interface for Plex Media Server.
# Copyright (C) 2026 SidusNare
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for
# more details.
#
# You should have received a copy of the GNU General Public License along
# with this program. If not, see <https://www.gnu.org/licenses/>.

"""plexdo - a command-line interface for Plex Media Server.

The public entry point is :func:`plexdo.cli.main`, exposed by the ``plexdo``
console script.
"""

import tomllib
from importlib import metadata
from pathlib import Path


def _version() -> str:
    """The version, which pyproject.toml alone defines.

    A source checkout reads it from there, so a version bumped since the
    last install is never reported stale; an installed copy has no
    pyproject.toml beside it and reads the metadata installed with it.
    """
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        project = {}
    if project.get("project", {}).get("name") == "plexdo":
        return str(project["project"]["version"])
    try:
        return metadata.version("plexdo")
    except metadata.PackageNotFoundError:
        return "0.0.0+unknown"


__version__ = _version()
__all__ = ["__version__"]
