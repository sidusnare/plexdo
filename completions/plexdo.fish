# fish completion for plexdo
#
# Installation:
#   Per user:    cp plexdo.fish ~/.config/fish/completions/
#   System-wide: cp plexdo.fish /usr/local/share/fish/vendor_completions.d/
#
# Completion for user IDs, library IDs, rating keys, playlists, and albums is
# read from the 15-minute cache under ~/.cache/plexdo that the list commands
# populate. A stale cache is refreshed in the background so completion never
# blocks; the values shown come from whatever is cached at that moment.

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

function __plexdo_cache_dir --description 'Directory holding the completion caches'
    # Memoised: reads the config file to honour [plex] cache_dir.
    if not set -q __plexdo_cache_resolved
        set -l py (__plexdo_python)
        set -g __plexdo_cache_resolved ($py -c '
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
' 2>/dev/null)
    end
    echo $__plexdo_cache_resolved
end

function __plexdo_cache_fresh --description 'True when the cache file is under 15 minutes old'
    set -l file $argv[1]
    test -f $file; or return 1
    set -l mtime (stat -c %Y $file 2>/dev/null; or stat -f %m $file 2>/dev/null)
    test -n "$mtime"; or return 1
    test (math (date +%s) - $mtime) -lt 900
end

function __plexdo_refresh --description 'Populate a cache in the background'
    # Guard on the binary existing: fish reports an unknown command before the
    # redirection applies, which would scribble on the prompt during a Tab.
    set -l prog
    if command -q plexdo
        set prog plexdo
    else if command -q plexdo
        set prog plexdo
    else
        return 0
    end
    command $prog $argv >/dev/null 2>&1 &
    disown 2>/dev/null
    return 0
end

function __plexdo_python --description 'python3, or python where that is all there is'
    if command -q python3
        echo python3
    else
        echo python
    end
end

function __plexdo_read_cache --description 'Emit value<TAB>description lines from a JSON cache'
    set -l file $argv[1]
    set -l field $argv[2]
    set -l desc ""
    test (count $argv) -ge 3; and set desc $argv[3]
    test -f $file; or return
    set -l __plexdo_py (__plexdo_python)
    $__plexdo_py -c '
import json, sys
path, field, desc = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    rows = json.load(open(path, encoding="utf-8"))
except Exception:
    sys.exit(0)
for row in rows:
    value = str(row.get(field, "")).strip()
    if not value:
        continue
    label = str(row.get(desc, "")).strip() if desc else ""
    print(f"{value}\t{label}" if label else value)
' $file $field "$desc" 2>/dev/null
end

# ---------------------------------------------------------------------------
# Positional-argument introspection
# ---------------------------------------------------------------------------

# Echo the positional arguments typed after the subcommand, one per line.
# Options that take a value consume the following token so it is not counted.
function __plexdo_positionals
    set -l toks (commandline -opc)
    set -e toks[1]
    set -l seen_cmd 0
    set -l skip 0
    for t in $toks
        if test $skip -eq 1
            set skip 0
            continue
        end
        switch $t
            case --m3u --album --sort --media-type --library-id -l --library -t --title -u --user --username -p --password -c --code -f --format --section -p --prefix --throttle -s --season
                set skip 1
                continue
            case '-*'
                continue
        end
        if test $seen_cmd -eq 0
            set seen_cmd 1
            continue
        end
        echo $t
    end
end

function __plexdo_at --description 'True when completing the Nth (0-based) positional'
    test (count (__plexdo_positionals)) -eq $argv[1]
end

function __plexdo_nth --description 'Echo the Nth (0-based) positional already typed'
    set -l vals (__plexdo_positionals)
    set -l idx (math $argv[1] + 1)
    test (count $vals) -ge $idx; and echo $vals[$idx]
end

# ---------------------------------------------------------------------------
# Value completers
# ---------------------------------------------------------------------------

function __plexdo_users
    set -l cache (__plexdo_cache_dir)/users.json
    __plexdo_cache_fresh $cache; or __plexdo_refresh list-users
    printf '%s\t%s\n' 0 "admin account"
    __plexdo_read_cache $cache id title
    __plexdo_read_cache $cache title
end

function __plexdo_libraries
    set -l cache (__plexdo_cache_dir)/libraries.json
    __plexdo_cache_fresh $cache; or __plexdo_refresh list-libraries
    __plexdo_read_cache $cache id title
    __plexdo_read_cache $cache title
end

function __plexdo_rating_keys
    set -l dir (__plexdo_cache_dir)
    set -l found 0
    for file in $dir/titles.*.json
        test -f $file; or continue
        set found 1
        if not __plexdo_cache_fresh $file
            set -l lib (string replace -r '.*/titles\.(.*)\.json$' '$1' $file)
            __plexdo_refresh list-titles $lib
        end
        __plexdo_read_cache $file ratingKey title
    end
    if test $found -eq 0
        __plexdo_refresh list-libraries
    end
    return 0
end

function __plexdo_playlists
    set -l user (__plexdo_nth $argv[1])
    test -n "$user"; or set user 0
    set -l cache (__plexdo_cache_dir)/playlists.$user.json
    __plexdo_cache_fresh $cache; or __plexdo_refresh list-playlists $user
    __plexdo_read_cache $cache title
end

# list-playlist accepts a playlist title or its ratingKey.
function __plexdo_playlists_or_keys
    __plexdo_playlists $argv[1]
    set -l user (__plexdo_nth $argv[1])
    test -n "$user"; or set user 0
    __plexdo_read_cache (__plexdo_cache_dir)/playlists.$user.json ratingKey title
end

function __plexdo_albums
    set -l lib (__plexdo_nth $argv[1])
    test -n "$lib"; or return
    set -l cache (__plexdo_cache_dir)/titles.$lib.json
    __plexdo_cache_fresh $cache; or __plexdo_refresh list-titles $lib
    __plexdo_read_cache $cache title | string replace -r ' - .*$' '' | sort -u
end

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

set -l plexdo_cmds list-libraries list-titles list-library list-show export-titles search status find-missing \
    list-users list-playlists list-playlist export-playlist remove-playlist \
    append-playlist clean-playlist show-metadata read rescan status find-missing build-interleaved \
    build-chronological build-randomize build-concatenated copy-playlist-all-users \
    copy-playlist-to-user copy-watched login write-config-example

# No bare filename completion anywhere; each rule opts in explicitly.
complete -c plexdo -f
complete -c plexdo -f

function __plexdo_no_subcommand -V plexdo_cmds
    not __fish_seen_subcommand_from $plexdo_cmds
end

for prog in plexdo
    complete -c $prog -n __plexdo_no_subcommand -a list-libraries -d 'List all Plex libraries'
    complete -c $prog -n __plexdo_no_subcommand -a list-titles -d 'List titles in a library'
    complete -c $prog -n __plexdo_no_subcommand -a list-library -d 'List titles in a library (alias)'
    complete -c $prog -n __plexdo_no_subcommand -a list-show -d 'List all episodes in a show'
    complete -c $prog -n __plexdo_no_subcommand -a export-titles -d 'Export a library to M3U or an HTML gallery'
    complete -c $prog -n __plexdo_no_subcommand -a search -d 'Search Plex for titles matching a query'
    complete -c $prog -n __plexdo_no_subcommand -a list-users -d 'List all managed/home users'
    complete -c $prog -n __plexdo_no_subcommand -a list-playlists -d 'List playlists for a user'
    complete -c $prog -n __plexdo_no_subcommand -a list-playlist -d 'List items in a specific playlist'
    complete -c $prog -n __plexdo_no_subcommand -a export-playlist -d 'Export a playlist to an M3U file'
    complete -c $prog -n __plexdo_no_subcommand -a clean-playlist -d 'Remove watched items from a playlist'
    complete -c $prog -n __plexdo_no_subcommand -a remove-playlist -d 'Delete a playlist from a user'
    complete -c $prog -n __plexdo_no_subcommand -a append-playlist -d 'Append items to an existing playlist'
    complete -c $prog -n __plexdo_no_subcommand -a show-metadata -d 'Display metadata for a single item'
    complete -c $prog -n __plexdo_no_subcommand -a read -d 'Stream a media file to stdout'
    complete -c $prog -n __plexdo_no_subcommand -a rescan -d 'Trigger a library rescan or show scan status'
    complete -c $prog -n __plexdo_no_subcommand -a status -d 'Show server identity, sessions, users, scans, and tasks'
    complete -c $prog -n __plexdo_no_subcommand -a find-missing -d 'Find gaps in episode numbering across every show'
    complete -c $prog -n __plexdo_no_subcommand -a build-interleaved -d 'Round-robin playlist from shows'
    complete -c $prog -n __plexdo_no_subcommand -a build-chronological -d 'Date-sorted playlist from shows and movies'
    complete -c $prog -n __plexdo_no_subcommand -a build-randomize -d 'Randomize a playlist into a new one'
    complete -c $prog -n __plexdo_no_subcommand -a build-concatenated -d 'Join several playlists end to end into one'
    complete -c $prog -n __plexdo_no_subcommand -a copy-playlist-all-users -d 'Copy a playlist to all managed users'
    complete -c $prog -n __plexdo_no_subcommand -a copy-playlist-to-user -d 'Copy a playlist to a specific user'
    complete -c $prog -n __plexdo_no_subcommand -a copy-watched -d 'Synchronise watched state between two users'
    complete -c $prog -n __plexdo_no_subcommand -a login -d 'Authenticate with plex.tv and save a token'
    complete -c $prog -n __plexdo_no_subcommand -a write-config-example -d 'Write a template config file'

    # Global flags: valid before or after the command name.
    complete -c $prog -l json -d 'Output machine-readable JSON instead of tables'
    complete -c $prog -s v -l verbose -d 'Print high-level progress to stderr'
    complete -c $prog -l debug -d 'Print detailed internal logs to stderr'
    complete -c $prog -l dry-run -d 'Show what would happen without mutating Plex'
    complete -c $prog -s W -l wide -d 'Do not shrink table columns to the terminal width'
    complete -c $prog -x -l throttle -d 'Seconds between requests in per-item operations; 0 disables'
    complete -c $prog -s h -l help -d 'Show this help message and exit'

    # -- positional arguments ------------------------------------------------
    complete -c $prog -n "__fish_seen_subcommand_from list-titles list-library export-titles read; and __plexdo_at 0" \
        -a '(__plexdo_libraries)' -d 'library'
    complete -c $prog -n "__fish_seen_subcommand_from rescan find-missing; and __plexdo_at 0" \
        -a '(__plexdo_libraries)' -d 'library'
    complete -c $prog -l include-specials -n '__fish_seen_subcommand_from find-missing' \
        -d 'Also check season 0'
    complete -c $prog -l include-partial -n '__fish_seen_subcommand_from clean-playlist' \
        -d 'Also remove part-played items'
    complete -c $prog -n "__fish_seen_subcommand_from list-show show-metadata; and __plexdo_at 0" \
        -a '(__plexdo_rating_keys)' -d 'item'
    complete -c $prog -n "__fish_seen_subcommand_from read; and __plexdo_at 1" \
        -a '(__plexdo_rating_keys)' -d 'item'
    complete -c $prog -n "__fish_seen_subcommand_from append-playlist; and not __plexdo_at 0; and not __plexdo_at 1" \
        -a '(__plexdo_rating_keys)' -d 'item'
    complete -c $prog -n "__fish_seen_subcommand_from build-interleaved build-chronological; and not __plexdo_at 0" \
        -a '(__plexdo_rating_keys)' -d 'item'

    complete -c $prog -n "__fish_seen_subcommand_from search list-playlists list-playlist export-playlist remove-playlist append-playlist clean-playlist build-randomize build-concatenated copy-playlist-all-users copy-playlist-to-user copy-watched; and __plexdo_at 0" \
        -a '(__plexdo_users)' -d 'user'
    complete -c $prog -n "__fish_seen_subcommand_from copy-watched; and __plexdo_at 1" \
        -a '(__plexdo_users)' -d 'user'
    complete -c $prog -n "__fish_seen_subcommand_from copy-playlist-to-user; and __plexdo_at 2" \
        -a '(__plexdo_users)' -d 'user'

    complete -c $prog -n "__fish_seen_subcommand_from list-playlist; and __plexdo_at 1" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'
    complete -c $prog -n "__fish_seen_subcommand_from export-playlist remove-playlist append-playlist clean-playlist build-randomize copy-playlist-all-users copy-playlist-to-user; and __plexdo_at 1" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'
    complete -c $prog -n "__fish_seen_subcommand_from build-concatenated; and not __plexdo_at 0; and not __plexdo_at 1" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'

    complete -c $prog -rF -n "__fish_seen_subcommand_from export-titles; and __plexdo_at 1"
    complete -c $prog -rF -n "__fish_seen_subcommand_from export-playlist; and __plexdo_at 2"

    # -- per-command options -------------------------------------------------
    complete -c $prog -x -s p -l prefix \
        -n '__fish_seen_subcommand_from list-playlist list-show export-playlist export-titles build-interleaved build-chronological build-randomize build-concatenated' \
        -d 'Rewrite exported paths onto this prefix'
    complete -c $prog -rF -l m3u \
        -n '__fish_seen_subcommand_from list-playlist list-show build-interleaved build-chronological build-randomize build-concatenated' \
        -d 'Also export an M3U file using Plex server paths'
    complete -c $prog -x -l album -n '__fish_seen_subcommand_from list-titles list-library export-titles' \
        -a '(__plexdo_albums 0)' -d 'Restrict to a single photo album'
    complete -c $prog -x -l sort -n '__fish_seen_subcommand_from export-titles' \
        -a 'alpha date random' -d 'Sort order'
    complete -c $prog -x -l media-type -n '__fish_seen_subcommand_from search' \
        -a 'movie show episode track photo album artist' -d 'Restrict to one media type'
    complete -c $prog -x -l library-id -n '__fish_seen_subcommand_from search' \
        -a '(__plexdo_libraries)' -d 'Restrict to one library'
    complete -c $prog -x -l section -n '__fish_seen_subcommand_from status' -a 'server sessions users accounts connections scans activities tasks' -d 'Show only one section'
    complete -c $prog -s s -l status -n '__fish_seen_subcommand_from rescan' -d 'Print all active scan jobs'
    complete -c $prog -s n -l now -n '__fish_seen_subcommand_from rescan' -d 'Cancel pending scans first'
    complete -c $prog -s o -l overwrite \
        -n '__fish_seen_subcommand_from copy-playlist-all-users copy-playlist-to-user build-interleaved build-chronological build-randomize build-concatenated' \
        -d 'Replace an existing playlist of the same name'
    complete -c $prog -l unique -n '__fish_seen_subcommand_from build-concatenated' \
        -d 'Skip an item an earlier playlist already contributed'
    complete -c $prog -x -s u -l user -n '__fish_seen_subcommand_from build-interleaved build-chronological build-randomize build-concatenated' \
        -a '(__plexdo_users)' -d 'Create the playlist for this user instead'
    complete -c $prog -s a -l all-users -n '__fish_seen_subcommand_from build-interleaved build-chronological build-randomize build-concatenated' \
        -d 'Create the playlist for every user on the server'
    complete -c $prog -l one-way -n '__fish_seen_subcommand_from copy-watched' -d 'Only write to the second user'
    complete -c $prog -x -s l -l library -n '__fish_seen_subcommand_from copy-watched' \
        -a '(__plexdo_libraries)' -d 'Restrict to one library'
    complete -c $prog -x -s t -l title -n '__fish_seen_subcommand_from copy-watched' \
        -a '(__plexdo_rating_keys)' -d 'Restrict to one item'
    complete -c $prog -l unwatch -n '__fish_seen_subcommand_from copy-watched' -d 'Propagate the unwatched state instead'
    complete -c $prog -x -s u -l username -n '__fish_seen_subcommand_from login' -d 'Plex username or email'
    complete -c $prog -x -s p -l password -n '__fish_seen_subcommand_from login' -d 'Plex password (INSECURE: visible in ps)'
    complete -c $prog -x -s c -l code -n '__fish_seen_subcommand_from login' -d 'Two-factor authentication code'
    complete -c $prog -s 2 -l two-factor -n '__fish_seen_subcommand_from login' -d 'Prompt for a two-factor code'
end
