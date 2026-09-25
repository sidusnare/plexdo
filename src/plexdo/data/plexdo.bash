#!/usr/bin/env bash
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
# of running any list-* command - completion triggers background refresh when
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
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-users
    # Commands accept an ID or a title, so both are insertable; each ID
    # carries its title as an annotation so it is clear which account it is.
    _plexdo_compreply_pairs < <(
        case "0" in "$cur"*) printf '0\tadmin account\n' ;; esac
        _plexdo_json_pairs "$cache" "id" "title"
        _plexdo_json_candidates "$cache" "title"
    )
}

# library_id - IDs and titles from the libraries cache; commands accept either.
_plexdo_complete_library_id() {
    local cache="$_PLEXDO_CACHE/libraries.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-libraries
    _plexdo_compreply_pairs < <(
        _plexdo_json_pairs "$cache" "id" "title"
        _plexdo_json_candidates "$cache" "title"
    )
}

# rating_key - ratingKeys aggregated from all titles.*.json cache files;
# triggers per-library background refresh for any stale file, and kicks off
# list-titles for each known library if no title cache exists at all.
_plexdo_complete_rating_key() {
    local found=0 f lib_id pairs=""
    COMPREPLY=()
    for f in "$_PLEXDO_CACHE"/titles.*.json; do
        [[ -f "$f" ]] || continue
        found=1
        if ! _plexdo_cache_is_fresh "$f"; then
            lib_id="${f##*/titles.}"
            lib_id="${lib_id%.json}"
            _plexdo_bg_refresh list-titles "$lib_id"
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
                _plexdo_bg_refresh list-titles "$lib_id"
            done < <( _plexdo_json_candidates "$lib_cache" "id" )
        else
            _plexdo_bg_refresh list-libraries
        fi
    }
}

# Complete a playlist by title OR ratingKey for a given user_id.
_plexdo_complete_playlist_id_or_name() {
    local user_id="$1"
    local cache="$_PLEXDO_CACHE/playlists.${user_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-playlists "$user_id"
    COMPREPLY=(); _plexdo_compreply < <(
        { _plexdo_json_candidates "$cache" "ratingKey"
          _plexdo_json_candidates "$cache" "title"; } | sort -u
    )
}

# playlist title for a given user_id (string, may contain spaces)
_plexdo_complete_playlist() {
    local user_id="$1"
    local cache="$_PLEXDO_CACHE/playlists.${user_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-playlists "$user_id"
    COMPREPLY=(); _plexdo_compreply < <( _plexdo_json_candidates "$cache" "title" )
}

# Album names for a given library_id - drawn from the titles cache.
# Emits the unique set of parentTitle values (album names) stored in the cache.
_plexdo_complete_album() {
    local lib_id="$1"
    local cache="$_PLEXDO_CACHE/titles.${lib_id}.json"
    _plexdo_cache_is_fresh "$cache" || _plexdo_bg_refresh list-titles "$lib_id"
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
    echo "list-libraries list-titles list-library list-users list-playlists list-playlist \
list-show show-metadata search read rescan status find-missing build-interleaved build-chronological build-randomize \
build-concatenated \
copy-playlist-all-users copy-playlist-to-user export-playlist remove-playlist \
append-playlist clean-playlist export-titles copy-watched login write-config-example"
}

_plexdo_global_flags() {
    echo "-f --format --json -v --verbose --debug --dry-run -W --wide --throttle -V --version -h --help"
}

_plexdo_output_formats() {
    echo "table json yaml csv clixml"
}

# Find the first non-flag positional word after the program name (= the sub-command).
_plexdo_find_cmd() {
    local i
    for (( i=1; i < cword; i++ )); do
        case "${words[$i]}" in
            --json|--verbose|--debug|--dry-run|--help) ;;
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
        case "$word" in --m3u|-f|--format|--section|-p|--prefix|--throttle|-s|--season|-l|--library|-u|--user) skip_next=1; continue ;; esac
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
        case "$word" in --m3u|-f|--format|--section|-p|--prefix|--throttle|-s|--season|-l|--library|-u|--user) skip_next=1; continue ;; esac
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

    # --m3u PATH -> file path
    if [[ "$prev" == "--m3u" ]]; then
        COMPREPLY=( $(compgen -f -- "$cur") )
        return
    fi

    # -u USER on the build commands -> a user id or title
    if [[ "$prev" == "-u" || "$prev" == "--user" ]]; then
        case "$cmd" in
            build-*) _plexdo_complete_user_id; return ;;
        esac
    fi

    # Flag completion
    if [[ "$cur" == --* ]]; then
        case "$cmd" in
            list-playlist|list-show)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --m3u --prefix -p" -- "$cur") ) ;;
            build-interleaved|build-chronological|build-randomize)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --m3u --prefix -p -o --overwrite --user -u --all-users -a" -- "$cur") ) ;;
            build-concatenated)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --m3u --prefix -p -o --overwrite --unique --user -u --all-users -a" -- "$cur") ) ;;
            export-playlist|export-titles)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --prefix -p" -- "$cur") ) ;;
            clean-playlist)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --include-partial" -- "$cur") ) ;;
            *)
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags)" -- "$cur") ) ;;
        esac
        return
    fi

    # No sub-command typed yet
    if [[ -z "$cmd" ]]; then
        COMPREPLY=( $(compgen -W "$(_plexdo_commands)" -- "$cur") )
        return
    fi

    pos="$(_plexdo_positional_count "$cmd")"

    case "$cmd" in

        list-libraries|list-users|write-config-example)
            COMPREPLY=() ;;

        # <library_id> [--album ALBUM]
        list-titles|list-library)
            if [[ "$prev" == "--album" ]]; then
                lib_id="$(_plexdo_nth_positional "$cmd" 0)"
                _plexdo_complete_album "$lib_id"
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --album" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <user_id>
        list-playlists)
            case $pos in
                0) _plexdo_complete_user_id ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist|ratingKey> [--m3u]
        list-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <rating_key> [--m3u]
        list-show|show-metadata)
            case $pos in
                0) _plexdo_complete_rating_key ;;
                *) COMPREPLY=() ;;
            esac ;;

        # [--section SECTION]
        status)
            if [[ "$prev" == "--section" ]]; then
                COMPREPLY=( $(compgen -W "server sessions users accounts connections scans activities tasks" -- "$cur") )
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --section" -- "$cur") )
            else
                COMPREPLY=()
            fi ;;

        # <show> [-l LIBRARY] [-A] [-s SEASONS] [--include-specials]
        find-missing)
            if [[ "$prev" == "-l" || "$prev" == "--library" ]]; then
                _plexdo_complete_library_id
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --library -l --all -A --season -s --include-specials" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_rating_key ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # [library_id] [-s/--status] [-n/--now]
        rescan)
            if [[ "$cur" == --* || "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --status -s --now -n" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # [-u USER] [-c CODE] [-2]
        login)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --username -u --password -p --code -c --two-factor -2" -- "$cur") )
            else
                COMPREPLY=()
            fi ;;

        # <user_a> <user_b> [-1] [-l ID] [-t KEY] [--unwatch]
        copy-watched)
            if [[ "$prev" == "--library" || "$prev" == "-l" ]]; then
                _plexdo_complete_library_id
            elif [[ "$prev" == "--title" || "$prev" == "-t" ]]; then
                _plexdo_complete_rating_key
            elif [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --one-way -1 --library -l --title -t --unwatch" -- "$cur") )
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

        # <name> <ratingKey...> [--m3u] [-o] [-u USER | -a]
        build-interleaved|build-chronological)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --m3u --overwrite -o --prefix -p --user -u --all-users -a" -- "$cur") )
                return
            fi
            case $pos in
                0) COMPREPLY=() ;;
                *) _plexdo_complete_rating_key ;;
            esac ;;

        # <user_id> <source> <dest> [--m3u] [-o] [-u USER | -a]
        build-randomize)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --m3u --overwrite -o --prefix -p --user -u --all-users -a" -- "$cur") )
                return
            fi
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <name> <playlist...> [--unique] [--m3u] [-o] [-u USER | -a]
        build-concatenated)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --unique --m3u --overwrite -o --prefix -p --user -u --all-users -a" -- "$cur") )
                return
            fi
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) COMPREPLY=() ;;
                *) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
            esac ;;

        # <source_user_id> <source_playlist> [-o]
        copy-playlist-all-users)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --overwrite -o" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_user_id ;;
                    1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                       _plexdo_complete_playlist_id_or_name "$uid" ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <source_user_id> <source_playlist> <user_id> <dest> [-o]
        copy-playlist-to-user)
            if [[ "$cur" == -* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --overwrite -o" -- "$cur") )
                return
            fi
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                2) _plexdo_complete_user_id ;;
                3) uid="$(_plexdo_nth_positional "$cmd" 2)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist>
        remove-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> [--include-partial]
        clean-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> <path>
        export-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                2) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                *) COMPREPLY=() ;;
            esac ;;

        # <user_id> <playlist> <ratingKey...>
        append-playlist)
            case $pos in
                0) _plexdo_complete_user_id ;;
                1) uid="$(_plexdo_nth_positional "$cmd" 0)"
                   _plexdo_complete_playlist_id_or_name "$uid" ;;
                *) _plexdo_complete_rating_key ;;
            esac ;;

        # <user_id> <query> [--media-type TYPE] [--library-id ID]
        search)
            if [[ "$prev" == "--media-type" ]]; then
                COMPREPLY=( $(compgen -W "movie show episode track photo album artist" -- "$cur") )
            elif [[ "$prev" == "--library-id" ]]; then
                _plexdo_complete_library_id
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --media-type --library-id" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_user_id ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        # <library_id> <path> [--sort alpha|date|random] [--album ALBUM]
        export-titles)
            if [[ "$prev" == "--sort" ]]; then
                COMPREPLY=( $(compgen -W "alpha date random" -- "$cur") )
            elif [[ "$prev" == "--album" ]]; then
                lib_id="$(_plexdo_nth_positional "$cmd" 0)"
                _plexdo_complete_album "$lib_id"
            elif [[ "$cur" == --* ]]; then
                COMPREPLY=( $(compgen -W "$(_plexdo_global_flags) --sort --album" -- "$cur") )
            else
                case $pos in
                    0) _plexdo_complete_library_id ;;
                    1) COMPREPLY=( $(compgen -f -- "$cur") ) ;;
                    *) COMPREPLY=() ;;
                esac
            fi ;;

        *)
            COMPREPLY=( $(compgen -W "$(_plexdo_commands)" -- "$cur") ) ;;
    esac
}

complete -F _plexdo_complete plexdo
