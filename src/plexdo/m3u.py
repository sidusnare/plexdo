# SPDX-License-Identifier: GPL-3.0-or-later

"""M3U export using Plex server filesystem paths."""

from pathlib import Path
from typing import List

from plexdo.constants import LOG, MediaItem
from plexdo.paths import PathMapper, identity
from plexdo.records import file_paths
from plexdo.titles import display_title


def write_m3u(
    sorted_items: List[MediaItem],
    path: str,
    map_path: PathMapper = identity,
) -> None:
    """Write an M3U playlist from the server's filesystem paths.

    *map_path* rewrites each path; it is the identity unless --prefix asked
    for something else.
    """
    lines: List[str] = ["#EXTM3U"]
    for item in sorted_items:
        duration_ms = getattr(item, "duration", None)
        seconds = int(duration_ms / 1000) if duration_ms else -1
        for file_path in file_paths(item):
            lines.append(f"#EXTINF:{seconds},{display_title(item)}")
            lines.append(map_path(file_path))

    output_path = Path(path).expanduser()
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOG.info("M3U written to %s (%d lines)", output_path, len(lines))
