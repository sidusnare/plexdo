#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
#
# Bash completion for plexdo - with cached ID / name completion.
#
# Requires: bash 4.0+, python3 (already required by plexdo itself)
#
# Installation:
#   Single session:  source plexdo.bash
#   Permanent:       cp plexdo.bash \
#                      ~/.local/share/bash-completion/completions/plexdo

# ---------------------------------------------------------------------------
# Cache helpers (15-minute TTL, written by the Python script as a side effect
# of running any *-list command - completion triggers background refresh when
# a cache file is stale or absent)
# ---------------------------------------------------------------------------

# Resolved on first use rather than at source time: it reads the config file
# to honour [plex] cache_dir, and spawning python for every new shell would be
# a noticeable startup cost.
_PLEXDO_CACHE=""

_plexdo_resolve_cache() {
    "$(_plexdo_python)" - << 'PYCACHE' 2>/dev/null
import configparser, os
from pathlib import Path
if os.name == "nt":
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    app = Path(base) / "PlexDo" if base else Path.home() / "AppData/Local/PlexDo"
    cfg_path, default = app / "plexdo.ini", app / "Cache"
else:
    cfg_path = Path("~/.local/etc/plexdo.ini").expanduser()
    default = Path("~/.cache/plexdo").expanduser()
value = ""
if cfg_path.exists():
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(cfg_path, encoding="utf-8")
        value = (parser.get("plex", "cache_dir", fallback="") or "").strip()
    except Exception:
        value = ""
print(Path(os.path.expandvars(value)).expanduser() if value else default)
PYCACHE
}
_PLEXDO_TTL=900   # seconds (15 minutes)

# Git Bash on Windows, and some minimal systems, ship "python" but not
# "python3".
_plexdo_python() {
    if command -v python3 >/dev/null 2>&1; then echo python3
    else echo python; fi
}

# bash 3.2 - the system bash still shipped by macOS - has no mapfile or
# readarray, so COMPREPLY is filled with a read loop instead. Redirecting into
# a function does not create a subshell, so the assignment survives.

# Emit "value<TAB>label" lines from a JSON cache, filtered to the current word.
_plexdo_json_pairs() {
    local file="$1" field="$2" label="$3"
    [[ -f "$file" ]] || return
    "$(_plexdo_python)" - "$cur" "$field" "$label" "$file" 2>/dev/null << 'PYJSON'
import json, sys
cur, field, label, path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
try:
    rows = json.load(open(path, encoding="utf-8"))
except Exception:
    sys.exit(0)
for row in rows:
    value = str(row.get(field, "")).strip()
    if not value or not value.startswith(cur):
        continue
    text = str(row.get(label, "")).strip()
    print(f"{value}\t{text}" if text else value)
PYJSON
}

# Fill COMPREPLY from "value<TAB>label" lines: show the label, insert the value.
#
# bash cannot attach descriptions to completions, but it only *inserts* a
# candidate once a single one remains; with several it merely lists them and
# inserts their common prefix. So the annotated forms are safe to display while
# there is still a choice, and the bare value is substituted the moment that
# choice collapses to one. Each annotated form starts with its own value, so
# the common prefix bash inserts remains a valid prefix of the real value.
_plexdo_compreply_pairs() {
    local value label
    local -a values labels
    COMPREPLY=()
    while IFS=$'\t' read -r value label; do
        [ -n "$value" ] || continue
        values+=("$value")
        if [ -n "$label" ]; then
            labels+=("$value  ($label)")
        else
            labels+=("$value")
        fi
    done
    if [ ${#values[@]} -eq 1 ]; then
        COMPREPLY=("${values[0]}")
    elif [ ${#values[@]} -gt 1 ]; then
        COMPREPLY=("${labels[@]}")
    fi
}

_plexdo_compreply() {
    local line
    while IFS= read -r line; do
        [ -n "$line" ] && COMPREPLY+=("$line")
    done
}

# Return 0 if cache file exists and is younger than $_PLEXDO_TTL seconds.
_plexdo_cache_is_fresh() {
    local file="$1"
    [[ -f "$file" ]] || return 1
    local mtime now
    now=$(date +%s)
    # stat syntax differs between Linux (-c) and macOS (-f)
    if ! mtime=$(stat -c %Y "$file" 2>/dev/null); then
        mtime=$(stat -f %m "$file" 2>/dev/null) || return 1
    fi
    (( now - mtime < _PLEXDO_TTL ))
}

# Run a plexdo sub-command in the background so its cache side-effect fires
# without blocking the completion prompt.  All output is suppressed.
_plexdo_bg_refresh() {
    local plexdo="${words[0]}"
    "$plexdo" "$@" >/dev/null 2>&1 &
    disown $! 2>/dev/null || true
}

# Emit one completion candidate per line from a JSON cache file.
#   $1  cache file path
#   $2  JSON key whose value becomes the completion word (e.g. "id", "title")
# Filters to entries whose value starts with $cur; passed as argv to avoid
# shell-quoting pitfalls.
_plexdo_json_candidates() {
    local file="$1" field="$2"
    [[ -f "$file" ]] || return
    python3 - "$cur" "$field" "$file" 2>/dev/null << 'PYEOF'
import json, sys
cur, field, path = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    for r in json.load(open(path, encoding="utf-8")):
        v = str(r.get(field, ""))
        if v.startswith(cur):
            print(v)
except Exception:
    pass
PYEOF
}

# ---------------------------------------------------------------------------
# Per-argument completion helpers
# ---------------------------------------------------------------------------

# user_id - "0" (admin), plus IDs and titles from the users cache. Commands
# accept either form, so both are offered.
_plexdo_complete_user_id() {
    local cache="$_PLEXDO_CACHE/users.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh users-list
    # Commands accept an ID or a title, so both are insertable; each ID
    # carries its title as an annotation so it is clear which account it is.
    _plexdo_compreply_pairs < <(
        if [[ 0 == "$cur"* ]]; then printf '0\tadmin account\n'; fi
        _plexdo_json_pairs "$cache" "id" "title"
        _plexdo_json_candidates "$cache" "title"
    )
}

# library_id - IDs and titles from the libraries cache; commands accept either.
_plexdo_complete_library_id() {
    local cache="$_PLEXDO_CACHE/libraries.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh libraries-list
    _plexdo_compreply_pairs < <(
        _plexdo_json_pairs "$cache" "id" "title"
        _plexdo_json_candidates "$cache" "title"
    )
}

# rating_key - ratingKeys aggregated from all titles.*.json cache files;
# triggers per-library background refresh for any stale file, and kicks off
# library-list for each known library if no title cache exists at all.
_plexdo_complete_rating_key() {
    local found=0 f lib_id pairs=""
    COMPREPLY=()
    for f in "$_PLEXDO_CACHE"/titles.*.json; do
        [[ -f "$f" ]] || continue
        found=1
        if ! _plexdo_cache_is_fresh "$f"; then
            lib_id="${f##*/titles.}"
            lib_id="${lib_id%.json}"
            _plexdo_bg_refresh library-list "$lib_id"
        fi
        # Keys are gathered from every library first, then rendered once, so
        # that a later library cannot overwrite an earlier one's matches.
        pairs+="$(_plexdo_json_pairs "$f" "ratingKey" "title")"$'\n'
    done
    if (( found )); then
        # Only the key is insertable here: fetchItem takes a numeric
        # ratingKey, so the title is shown purely to identify the item.
        _plexdo_compreply_pairs <<< "$pairs"
        return
    fi
    {
        local lib_cache="$_PLEXDO_CACHE/libraries.json"
        if [[ -f "$lib_cache" ]]; then
            local lib_id
            while IFS= read -r lib_id; do
                _plexdo_bg_refresh library-list "$lib_id"
            done < <( _plexdo_json_candidates "$lib_cache" "id" )
        else
            _plexdo_bg_refresh libraries-list
        fi
    }
}

# Complete a playlist by title OR ratingKey for a given user_id.
_plexdo_complete_playlist_id_or_name() {
    local user_id="$1"
    local cache="$_PLEXDO_CACHE/playlists.${user_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh playlists-list "$user_id"
    COMPREPLY=(); _plexdo_compreply < <(
        { _plexdo_json_candidates "$cache" "ratingKey"
          _plexdo_json_candidates "$cache" "title"; } | sort -u
    )
}

# playlist title for a given user_id (string, may contain spaces)
_plexdo_complete_playlist() {
    local user_id="$1"
    local cache="$_PLEXDO_CACHE/playlists.${user_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh playlists-list "$user_id"
    COMPREPLY=(); _plexdo_compreply < <( _plexdo_json_candidates "$cache" "title" )
}

# Album names for a given library_id - drawn from the titles cache.
# Emits the unique set of parentTitle values (album names) stored in the cache.
_plexdo_complete_album() {
    local lib_id="$1"
    local cache="$_PLEXDO_CACHE/titles.${lib_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh library-list "$lib_id"
    COMPREPLY=(); _plexdo_compreply < <(
        python3 - "$cur" "$cache" 2>/dev/null << 'PYEOF'
import json, sys
cur, path = sys.argv[1], sys.argv[2]
try:
    seen = set()
    for r in json.load(open(path, encoding="utf-8")):
        t = str(r.get("title", ""))
        # titles for photo entries are "Album - Photo", strip after " - "
        album = t.split(" - ")[0] if " - " in t else t
        if album and album not in seen and album.startswith(cur):
            seen.add(album)
            print(album)
except Exception:
    pass
PYEOF
    )
}

# ---------------------------------------------------------------------------
# Positional-argument introspection helpers
# ---------------------------------------------------------------------------

_plexdo_commands() {
    echo "album-list albums-list libraries-list library-list login logout \
merge-build missing-find player-remote-play playlist-build playlist-clean \
playlist-copy playlist-export playlist-list playlist-remove playlists-list \
read rescan search set-pin show-list show-metadata show-watched-cp status \
titles-export users-list wait write-config-example write-secrets-example"
}

# The mode flag given to playlist-build or playlist-copy, as its long name
# without the dashes; nothing when none has been typed yet. The mode decides
# what each positional argument is.
_plexdo_mode() {
    local i
    for (( i=1; i < cword; i++ )); do
        case "${words[$i]}" in
            -I|--interleaved) echo interleaved; return ;;
            -C|--chronological) echo chronological; return ;;
            -R|--randomize) echo randomize; return ;;
            -A|--append|--all) echo all-or-append; return ;;
            -T|--to) echo to; return ;;
        esac
    done
}

_plexdo_global_flags() {
    echo "-f --format --json -v --verbose --debug --debug-log --dry-run -W --wide --throttle -V --version -h --help"
}

_plexdo_output_formats() {
    echo "table json yaml csv clixml"
}

# Find the first non-flag positional word after the program name (= the sub-command).
# A global option given before it takes its value with it.
_plexdo_find_cmd() {
    local i skip_next=0
    for (( i=1; i < cword; i++ )); do
        if (( skip_next )); then skip_next=0; continue; fi
        case "${words[$i]}" in
            -f|--format|--throttle|--debug-log) skip_next=1 ;;
            -*) ;;
            *) echo "${words[$i]}"; return ;;
        esac
    done
}

# Count non-flag positional arguments typed so far after the sub-command.
# --m3u consumes its following PATH token so it doesn't inflate the count.
_plexdo_positional_count() {
    local cmd="$1"
    local found_cmd=0 count=0 skip_next=0 i word
    for (( i=1; i < cword; i++ )); do
        word="${words[$i]}"
        if (( skip_next )); then skip_next=0; continue; fi
        case "$word" in --m3u|-f|--format|--section|-p|--prefix|--throttle|--season|-l|--library|-u|--user|--port|--player-user|--server-url|--ratio|--debug-log) skip_next=1; continue ;; esac
        # -s takes a value only where it is --session or --season.
        if [[ "$word" == -s ]]; then
            case "$cmd" in wait|missing-find) skip_next=1 ;; esac
            continue
        fi
        if [[ "$word" == -* ]]; then continue; fi
        if (( ! found_cmd )); then
            [[ "$word" == "$cmd" ]] && found_cmd=1
            continue
        fi
        (( count++ ))
    done
    echo "$count"
}

# Return the Nth (0-based) non-flag positional argument after the sub-command.
_plexdo_nth_positional() {
    local cmd="$1" n="$2"
    local found_cmd=0 count=0 skip_next=0 i word
    for (( i=1; i < cword; i++ )); do
        word="${words[$i]}"
        if (( skip_next )); then skip_next=0; continue; fi
        case "$word" in --m3u|-f|--format|--section|-p|--prefix|--throttle|--season|-l|--library|-u|--user|--port|--player-user|--server-url|--ratio|--debug-log) skip_next=1; continue ;; esac
        # -s takes a value only where it is --session or --season.
        if [[ "$word" == -s ]]; then
            case "$cmd" in wait|missing-find) skip_next=1 ;; esac
            continue
        fi
        if [[ "$word" == -* ]]; then continue; fi
        if (( ! found_cmd )); then
            [[ "$word" == "$cmd" ]] && found_cmd=1
            continue
        fi
        if (( count == n )); then echo "$word"; return; fi
        (( count++ ))
    done
}

# ---------------------------------------------------------------------------
# Main completion function
# ---------------------------------------------------------------------------

_plexdo_complete() {
    local cur prev words cword
    words=( "${COMP_WORDS[@]}" )
    cword=$COMP_CWORD
    cur="${words[$cword]}"
    prev="${words[$cword-1]}"

    local cmd pos uid
    cmd="$(_plexdo_find_cmd)"

    # --m3u PATH, --debug-log PATH -> file path
    if [[ "$prev" == "--m3u" || "$prev" == "--debug-log" ]]; then
        COMPREPLY=(); _plexdo_compreply < <(compgen -f -- "$cur")
        return
    fi

    # -u USER on playlist-build and merge-build -> a user id or title
    if [[ "$prev" == "-u" || "$prev" == "--user" ]]; then
        case "$cmd" in
            playlist-build|merge-build) _plexdo_complete_user_id; return ;;
        esac
    fi

    # Flag completion
    if [[ "$cur" == --* ]]; then
        case "$cmd" in
            playlist-list|show-list)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --m3u --prefix -p" -- "$cur") ;;
            playlist-build)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --interleaved -I --chronological -C --randomize -R --append -A --m3u --prefix -p -o --overwrite --user -u --all-users -a" -- "$cur") ;;
            playlist-copy)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --all -A --to -T --overwrite -o" -- "$cur") ;;
            merge-build)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --m3u --prefix -p -o --overwrite --ratio --stop-short -s --unique -U --user -u --all-users -a" -- "$cur") ;;
            playlist-export|titles-export)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --prefix -p" -- "$cur") ;;
            playlist-clean)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --include-partial" -- "$cur") ;;
            write-config-example|write-secrets-example)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --overwrite -o" -- "$cur") ;;
            wait)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) -s --session -r --rating-key -a --all -i --interval --fast-interval --no-credits --offset --paused --now" -- "$cur") ;;
            player-remote-play)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --port --player-user --server-url" -- "$cur") ;;
            login)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --username -u --password -p --save-password --code -c --two-factor -2" -- "$cur") ;;
            logout)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --username -u" -- "$cur") ;;
            set-pin)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --remove" -- "$cur") ;;
            *)
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags)" -- "$cur") ;;
        esac
        return
    fi

    # No sub-command typed yet
    if [[ -z "$cmd" ]]; then
        COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_commands)" -- "$cur")
        return
    fi

    pos="$(_plexdo_positional_count "$cmd")"

    case "$cmd" in

        libraries-list|users-list)
            COMPREPLY=() ;;

        # [-o]
        write-config-example|write-secrets-example)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --overwrite -o" -- "$cur")
            else
                COMPREPLY=()
            fi ;;

        # <library_id>
        albums-list)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags)" -- "$cur")
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <library_id> [--album ALBUM]
        library-list)
            if [[ "$prev" == "--album" ]]; then
                lib_id="$(_plexdo_nth_positional "$cmd" 0)"
                _plexdo_complete_album "$lib_id"
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --album" -- "$cur")
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <user_id>
        playlists-list)
            case $pos in
                0) _plexdo_complete_user_id ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist|ratingKey> [--m3u]
        playlist-list)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <rating_key> [--m3u]
        show-list|show-metadata|album-list)
            case $pos in
                0) _plexdo_complete_rating_key ;;
                *) COMPREPLY=() ;;
            esac ;;

        # [--section SECTION]
        status)
            if [[ "$prev" == "--section" ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "server sessions users accounts connections scans activities tasks" -- "$cur")
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --section" -- "$cur")
            else
                COMPREPLY=()
            fi ;;

        # <show> [-l LIBRARY] [-A] [-s SEASONS] [--include-specials]
        missing-find)
            if [[ "$prev" == "-l" || "$prev" == "--library" ]]; then
                _plexdo_complete_library_id
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --library -l --all -A --season -s --include-specials" -- "$cur")
            else
                case $pos in
                    0) _plexdo_complete_rating_key ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # [library_id] [-s/--status] [-n/--now]
        rescan)
            if [[ "$cur" == --* || "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --status -s --now -n" -- "$cur")
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # [-u USER] [-p PASS] [--save-password] [-c CODE] [-2]
        login)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --username -u --password -p --save-password --code -c --two-factor -2" -- "$cur")
            else
                COMPREPLY=()
            fi ;;

        # [-u USER]; the saved sessions' names are not cached
        logout)
            COMPREPLY=() ;;

        # <user_id> [--remove]
        set-pin)
            case $pos in
                0) _plexdo_complete_user_id ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_a> <user_b> [-1] [-l ID] [-t KEY] [--unwatch]
        show-watched-cp)
            if [[ "$prev" == "--library" || "$prev" == "-l" ]]; then
                _plexdo_complete_library_id
            elif [[ "$prev" == "--title" || "$prev" == "-t" ]]; then
                _plexdo_complete_rating_key
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --one-way -1 --library -l --title -t --unwatch" -- "$cur")
            else
                case $pos in
                    0|1) _plexdo_complete_user_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <library_id> <rating_key>
        read)
            case $pos in
                0) _plexdo_complete_library_id ;;
                1) _plexdo_complete_rating_key ;;
                *) COMPREPLY=() ;;
            esac ;;

        # (-I | -C) <name> <ratingKey...> [--m3u] [-o] [-u USER | -a]
        # -R <user_id> <source> <dest> [--m3u] [-o] [-u USER | -a]
        # -A <user_id> <playlist> <ratingKey...>
        playlist-build)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --interleaved -I --chronological -C --randomize -R --append -A --m3u --overwrite -o --prefix -p --user -u --all-users -a" -- "$cur")
                return
            fi
            case "$(_plexdo_mode)" in
                interleaved|chronological)
                    case $pos in
                        0) COMPREPLY=() ;;
                        *) _plexdo_complete_rating_key ;;
                    esac ;;
                randomize)
                    case $pos in
                        0) _plexdo_complete_user_id ;;
                        1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                           _plexdo_complete_playlist_id_or_name "$uid" ;;
                        *) COMPREPLY=() ;;
                    esac ;;
                all-or-append)
                    case $pos in
                        0) _plexdo_complete_user_id ;;
                        1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                           _plexdo_complete_playlist_id_or_name "$uid" ;;
                        *) _plexdo_complete_rating_key ;;
                    esac ;;
                # No mode yet, so nothing says what this argument is.
                *) COMPREPLY=(); _plexdo_compreply < <(compgen -W "-I -C -R -A" -- "$cur") ;;
            esac ;;

        # <user_id> <name> <first> <second> [--ratio A:B] [-s] [-U] [--m3u] [-o] [-u USER | -a]
        merge-build)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --ratio --stop-short -s --unique -U --m3u --overwrite -o --prefix -p --user -u --all-users -a" -- "$cur")
                return
            fi
            case $pos in
                0) _plexdo_complete_user_id ;;
                2|3) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # -A <source_user_id> <source_playlist> [-o]
        # -T <source_user_id> <source_playlist> <user_id> <dest> [-o]
        playlist-copy)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --all -A --to -T --overwrite -o" -- "$cur")
                return
            fi
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                2) if [[ "$(_plexdo_mode)" == to ]]; then
                       _plexdo_complete_user_id
                   else
                       COMPREPLY=()
                   fi ;;
                3) if [[ "$(_plexdo_mode)" == to ]]; then
                       uid="$(_plexdo_nth_positional "$cmd" 2)"
                       _plexdo_complete_playlist_id_or_name "$uid"
                   else
                       COMPREPLY=()
                   fi ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist>
        playlist-remove)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # [-s KEY] [-r KEY] [-a] [-i SECONDS] [--fast-interval SECONDS] [--no-credits] [--offset SECONDS] [--paused SECONDS] [--now]
        wait)
            case "$prev" in
                -r|--rating-key) _plexdo_complete_rating_key ;;
                -s|--session|-i|--interval|--fast-interval|--offset|--paused) COMPREPLY=() ;;
                *) COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) -s --session -r --rating-key -a --all -i --interval --fast-interval --no-credits --offset --paused --now" -- "$cur") ;;
            esac ;;

        # <host> <ratingKey> [--port PORT] [--player-user USER] [--server-url URL]
        player-remote-play)
            case "$prev" in --port|--player-user|--server-url) COMPREPLY=(); return ;; esac
            case $pos in
                0) COMPREPLY=(); _plexdo_compreply < <(compgen -A hostname -- "$cur") ;;
                1) _plexdo_complete_rating_key ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> [--include-partial]
        playlist-clean)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> <path>
        playlist-export)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                2) COMPREPLY=(); _plexdo_compreply < <(compgen -f -- "$cur") ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <query> [--media-type TYPE] [--library-id ID]
        search)
            if [[ "$prev" == "--media-type" ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "movie show episode track photo album artist" -- "$cur")
            elif [[ "$prev" == "--library-id" ]]; then
                _plexdo_complete_library_id
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --media-type --library-id" -- "$cur")
            else
                case $pos in
                    0) _plexdo_complete_user_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <library_id> <path> [--sort alpha|date|random] [--album ALBUM]
        titles-export)
            if [[ "$prev" == "--sort" ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "alpha date random" -- "$cur")
            elif [[ "$prev" == "--album" ]]; then
                lib_id="$(_plexdo_nth_positional "$cmd" 0)"
                _plexdo_complete_album "$lib_id"
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_global_flags) --sort --album" -- "$cur")
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    1) COMPREPLY=(); _plexdo_compreply < <(compgen -f -- "$cur") ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        *)
            COMPREPLY=(); _plexdo_compreply < <(compgen -W "$(_plexdo_commands)" -- "$cur") ;;
    esac
}

complete -F _plexdo_complete plexdo
