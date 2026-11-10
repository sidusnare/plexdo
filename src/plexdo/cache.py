# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)

"""Completion cache written as a side effect of list commands."""

import json
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from plexdo.config import cached_config, config_optional
from plexdo.constants import CONFIG_PATH, DEFAULT_CACHE_DIR, LOG


def cache_dir() -> Path:
    """Return the completion cache directory.

    plex: cache_dir overrides the platform default. The config is only
    consulted when it exists, so this stays usable before `plexdo login` has
    ever been run.
    """
    if CONFIG_PATH.exists():
        configured = config_optional(cached_config(), "cache_dir")
        if configured:
            return Path(configured).expanduser()
    return DEFAULT_CACHE_DIR


def write_cache(name: str, data: list[dict[str, Any]]) -> None:
    """Atomically write data to the completion cache, ignoring errors."""
    try:
        directory = cache_dir()
        directory.mkdir(parents=True, exist_ok=True)
        cache_file = directory / f"{name}.json"
        tmp = cache_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(data), encoding="utf-8")
        tmp.replace(cache_file)
        LOG.debug("Cache updated: %s", cache_file)
    except OSError:
        pass


# What may not appear in a file name on one platform or another. Replaced
# rather than encoded, so that each completion script can name the same
# file with one substitution of its own.
_UNSAFE_IN_NAMES = re.compile(r'[/\\:*?"<>|\x00-\x1f]')


def cache_key(word: Any) -> str:
    """A word a user may type for a user or library, as part of a file name."""
    return _UNSAFE_IN_NAMES.sub("_", str(word))


def write_word_caches(
    kind: str, words: Iterable[Any], data: list[dict[str, Any]]
) -> None:
    """Write data once for each word its subject goes by.

    The cache named for a numeric ID is no use to a completion script
    holding "Alice": it would have to resolve the title as plexdo does. So
    the same rows are filed under every spelling plexdo knows - the ID, the
    title, and whatever was typed - as kind-by-word.WORD.json, and a script
    looks up the word it has.
    """
    keys = dict.fromkeys(
        cache_key(word) for word in words if word not in (None, "")
    )
    for key in keys:
        write_cache(f"{kind}-by-word.{key}", data)
