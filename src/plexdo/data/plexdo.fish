# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
#
# fish completion for plexdo
#
# Installation:
#   Per user:    cp plexdo.fish ~/.config/fish/completions/
#   System-wide: cp plexdo.fish /usr/local/share/fish/vendor_completions.d/
#
# Completion for user IDs, library IDs, rating keys, playlists, and albums is
# read from the 15-minute cache that the list commands populate, in plex:
# cache_dir or else $XDG_CACHE_HOME/plexdo, by default ~/.cache/plexdo. A
# stale cache is refreshed in the background so completion never blocks; the values shown come from whatever is cached at that moment.

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

function __plexdo_cache_dir --description 'Directory holding the completion caches'
    # Memoised: reads the config file to honour plex: cache_dir.
    if not set -q __plexdo_cache_resolved
        set -l py (__plexdo_python)
        set -g __plexdo_cache_resolved ($py -c '
import json, os
from pathlib import Path
def xdg(name, fallback):
    value = os.environ.get(name, "")
    if value and Path(value).is_absolute():
        return Path(value)
    return Path(fallback).expanduser()
if os.name == "nt":
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    app = Path(root) / "PlexDo" if root else Path.home() / "AppData/Local/PlexDo"
    cfg_path, default = app / "config.yaml", app / "Cache"
else:
    cfg_path = xdg("XDG_CONFIG_HOME", "~/.config") / "plexdo" / "config.yaml"
    default = xdg("XDG_CACHE_HOME", "~/.cache") / "plexdo"
try:
    lines = cfg_path.read_text(encoding="utf-8").splitlines()
except OSError:
    lines = []
# The one value wanted is a scalar directly under plex:, so the file is
# read a line at a time; PyYAML may not be importable from this python.
value, in_plex, dq, sq = "", False, chr(34), chr(39)
for line in lines:
    text = line.strip()
    if not text or text.startswith("#") or text == "---":
        continue
    if line[:1] not in (" ", chr(9)):
        in_plex = text.split(":")[0].strip() == "plex"
        continue
    key, colon, rest = text.partition(":")
    if not (in_plex and colon and key.strip() == "cache_dir"):
        continue
    rest = rest.strip()
    if rest[:1] == dq:
        try:
            rest = json.JSONDecoder().raw_decode(rest)[0]
        except ValueError:
            rest = rest.strip(dq)
    elif rest[:1] == sq and sq in rest[1:]:
        rest = rest[1:rest.rindex(sq)].replace(sq + sq, sq)
    else:
        rest = rest.split(" #")[0].strip()
    value = "" if rest in ("null", "~") else str(rest)
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
    set -l cmd
    set -l skip 0
    for t in $toks
        if test $skip -eq 1
            set skip 0
            continue
        end
        switch $t
            case --m3u --album --sort --media-type --library-id -l --library -t --title --type --path --filter --category --update -u --user --username -p --password -c --code -f --format --section -p --prefix --throttle --season --port --player-user --server-url --ratio --debug-log
                set skip 1
                continue
            case -s
                # -s takes a value only where it is --session or --season.
                contains -- "$cmd" wait find-missing; and set skip 1
                continue
            case '-*'
                continue
        end
        if test $seen_cmd -eq 0
            set seen_cmd 1
            set cmd $t
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

function __plexdo_mode --description 'True when the mode flag typed is one of those named'
    # playlist-build and playlist-copy take a flag saying what their
    # positional arguments are; with none typed yet, nothing matches.
    for t in (commandline -opc)
        switch $t
            case -I --interleaved
                contains -- interleaved $argv; and return 0
                return 1
            case -C --chronological
                contains -- chronological $argv; and return 0
                return 1
            case -R --randomize
                contains -- randomize $argv; and return 0
                return 1
            case -A --append --all
                contains -- all-or-append $argv; and return 0
                return 1
            case -M --merge
                contains -- merge $argv; and return 0
                return 1
            case -T --to
                contains -- to $argv; and return 0
                return 1
        end
    end
    return 1
end

# ---------------------------------------------------------------------------
# Value completers
# ---------------------------------------------------------------------------

function __plexdo_users
    set -l cache (__plexdo_cache_dir)/users.json
    __plexdo_cache_fresh $cache; or __plexdo_refresh users-list
    printf '%s\t%s\n' 0 "admin account"
    __plexdo_read_cache $cache id title
    __plexdo_read_cache $cache title
end

function __plexdo_libraries
    set -l cache (__plexdo_cache_dir)/libraries.json
    __plexdo_cache_fresh $cache; or __plexdo_refresh libraries-list
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
            __plexdo_refresh library-list $lib
        end
        __plexdo_read_cache $file ratingKey title
    end
    if test $found -eq 0
        __plexdo_refresh libraries-list
    end
    return 0
end

function __plexdo_word_key --description 'A user or library word as plexdo names its by-word cache'
    # Every character a file name cannot hold becomes "_", as plexdo's
    # cache_key does. plexdo writes the by-word cache for the ID, the title,
    # and the word as typed, so whichever is on the command line finds it.
    string replace -ra '[/\\\\:*?"<>|]' _ -- $argv[1]
end

function __plexdo_playlists
    set -l user (__plexdo_nth $argv[1])
    test -n "$user"; or set user 0
    set -l cache (__plexdo_cache_dir)/playlists-by-word.(__plexdo_word_key $user).json
    __plexdo_cache_fresh $cache; or __plexdo_refresh playlists-list $user
    __plexdo_read_cache $cache title
end

# playlist-list accepts a playlist title or its ratingKey.
function __plexdo_playlists_or_keys
    __plexdo_playlists $argv[1]
    set -l user (__plexdo_nth $argv[1])
    test -n "$user"; or set user 0
    __plexdo_read_cache (__plexdo_cache_dir)/playlists-by-word.(__plexdo_word_key $user).json ratingKey title
end

function __plexdo_albums
    set -l lib (__plexdo_nth $argv[1])
    test -n "$lib"; or return
    set -l cache (__plexdo_cache_dir)/titles-by-word.(__plexdo_word_key $lib).json
    __plexdo_cache_fresh $cache; or __plexdo_refresh library-list $lib
    __plexdo_read_cache $cache title | sort -u
end

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

set -l plexdo_cmds album-list find-missing libraries-list library-list login logout \
    metadata player-remote-play playlist-build playlist-clean \
    playlist-copy playlist-export playlist-list playlist-remove playlists-list \
    read rescan search set-pin show-list show-watched-cp status titles-export \
    users-list wait write-config-example write-secrets-example

# No bare filename completion anywhere; each rule opts in explicitly.
complete -c plexdo -f
complete -c plexdo -f

function __plexdo_no_subcommand -V plexdo_cmds
    not __fish_seen_subcommand_from $plexdo_cmds
end

for prog in plexdo

    complete -c $prog -n __plexdo_no_subcommand -a album-list -d 'Show one album with its played state and progress'
    complete -c $prog -n __plexdo_no_subcommand -a find-missing -d 'Find gaps in the episode numbering of a show'
    complete -c $prog -n __plexdo_no_subcommand -a libraries-list -d 'List the server\'s libraries'
    complete -c $prog -n __plexdo_no_subcommand -a library-list -d 'List what a library holds, by type or by folder'
    complete -c $prog -n __plexdo_no_subcommand -a login -d 'Sign in to plex.tv and save the token'
    complete -c $prog -n __plexdo_no_subcommand -a logout -d 'Sign out of plex.tv and remove the saved tokens'
    complete -c $prog -n __plexdo_no_subcommand -a metadata -d 'Show or update the metadata of one item'
    complete -c $prog -n __plexdo_no_subcommand -a player-remote-play -d 'Tell a player, reached directly, to play an item'
    complete -c $prog -n __plexdo_no_subcommand -a playlist-build -d 'Build a playlist, or add items to one'
    complete -c $prog -n __plexdo_no_subcommand -a playlist-clean -d 'Remove the watched items from a playlist'
    complete -c $prog -n __plexdo_no_subcommand -a playlist-copy -d 'Copy a playlist to one user, or to all of them'
    complete -c $prog -n __plexdo_no_subcommand -a playlist-export -d 'Export a playlist to an M3U file'
    complete -c $prog -n __plexdo_no_subcommand -a playlist-list -d 'List the items in a playlist'
    complete -c $prog -n __plexdo_no_subcommand -a playlist-remove -d 'Delete a playlist'
    complete -c $prog -n __plexdo_no_subcommand -a playlists-list -d 'List a user\'s playlists'
    complete -c $prog -n __plexdo_no_subcommand -a read -d 'Stream a media file to stdout'
    complete -c $prog -n __plexdo_no_subcommand -a rescan -d 'Rescan libraries, or show the scans under way'
    complete -c $prog -n __plexdo_no_subcommand -a search -d 'Search for titles matching a query'
    complete -c $prog -n __plexdo_no_subcommand -a set-pin -d 'Save or remove a Plex Home member\'s PIN'
    complete -c $prog -n __plexdo_no_subcommand -a show-list -d 'List a show\'s episodes'
    complete -c $prog -n __plexdo_no_subcommand -a show-watched-cp -d 'Sync watched state and resume points of two users'
    complete -c $prog -n __plexdo_no_subcommand -a status -d 'Show the server\'s sessions, users, scans, and tasks'
    complete -c $prog -n __plexdo_no_subcommand -a titles-export -d 'Export a library to an M3U file or photo gallery'
    complete -c $prog -n __plexdo_no_subcommand -a users-list -d 'List the server\'s users'
    complete -c $prog -n __plexdo_no_subcommand -a wait -d 'Sleep until a session\'s current play is over'
    complete -c $prog -n __plexdo_no_subcommand -a write-config-example -d 'Write a template configuration file'
    complete -c $prog -n __plexdo_no_subcommand -a write-secrets-example -d 'Write an example secrets file, or print it'

    # Global flags: valid before or after the command name.
    complete -c $prog -l json -d 'Output machine-readable JSON instead of tables'
    complete -c $prog -s v -l verbose -d 'Print high-level progress to stderr'
    complete -c $prog -l debug -d 'Print detailed internal logs to stderr'
    complete -c $prog -rF -l debug-log -d 'Append the debug logs, profiled and timestamped, to a file'
    complete -c $prog -l dry-run -d 'Show what would happen without mutating Plex'
    complete -c $prog -s W -l wide -d 'Do not shrink table columns to the terminal width'
    complete -c $prog -x -l throttle -d 'Seconds between requests in per-item operations; 0 disables'
    complete -c $prog -s h -l help -d 'Show this help message and exit'

    # -- positional arguments ------------------------------------------------
    complete -c $prog -n "__fish_seen_subcommand_from library-list titles-export; and __plexdo_at 0" \
        -a '(__plexdo_libraries)' -d 'library'
    complete -c $prog -n "__fish_seen_subcommand_from rescan; and __plexdo_at 0" \
        -a '(__plexdo_libraries)' -d 'library'
    complete -c $prog -l include-specials -n '__fish_seen_subcommand_from find-missing' \
        -d 'Also check season 0'
    complete -c $prog -l include-partial -n '__fish_seen_subcommand_from playlist-clean' \
        -d 'Also remove part-played items'
    complete -c $prog -n "__fish_seen_subcommand_from show-list metadata album-list read find-missing; and __plexdo_at 0" \
        -a '(__plexdo_rating_keys)' -d 'item'
    complete -c $prog -n "__fish_seen_subcommand_from player-remote-play; and __plexdo_at 0" \
        -a '(__fish_print_hostnames)' -d 'player host'
    complete -c $prog -n "__fish_seen_subcommand_from player-remote-play; and __plexdo_at 1" \
        -a '(__plexdo_rating_keys)' -d 'item'
    # playlist-build: what an argument is depends on the mode flag.
    complete -c $prog -n "__fish_seen_subcommand_from playlist-build; and __plexdo_mode all-or-append; and not __plexdo_at 0; and not __plexdo_at 1" \
        -a '(__plexdo_rating_keys)' -d 'item'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-build; and __plexdo_mode interleaved chronological; and not __plexdo_at 0" \
        -a '(__plexdo_rating_keys)' -d 'item'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-build; and __plexdo_mode randomize all-or-append merge; and __plexdo_at 0" \
        -a '(__plexdo_users)' -d 'user'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-build; and __plexdo_mode randomize all-or-append; and __plexdo_at 1" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'

    complete -c $prog -n "__fish_seen_subcommand_from search playlists-list playlist-list playlist-export playlist-remove playlist-clean playlist-copy show-watched-cp set-pin; and __plexdo_at 0" \
        -a '(__plexdo_users)' -d 'user'
    complete -c $prog -n "__fish_seen_subcommand_from show-watched-cp; and __plexdo_at 1" \
        -a '(__plexdo_users)' -d 'user'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-copy; and __plexdo_mode to; and __plexdo_at 2" \
        -a '(__plexdo_users)' -d 'user'

    complete -c $prog -n "__fish_seen_subcommand_from playlist-list; and __plexdo_at 1" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-export playlist-remove playlist-clean playlist-copy; and __plexdo_at 1" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-build; and __plexdo_mode merge; and __plexdo_at 2" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'
    complete -c $prog -n "__fish_seen_subcommand_from playlist-build; and __plexdo_mode merge; and __plexdo_at 3" \
        -a '(__plexdo_playlists_or_keys 0)' -d 'playlist'

    complete -c $prog -rF -n "__fish_seen_subcommand_from titles-export; and __plexdo_at 1"
    complete -c $prog -rF -n "__fish_seen_subcommand_from playlist-export; and __plexdo_at 2"

    # -- per-command options -------------------------------------------------
    complete -c $prog -x -s p -l prefix \
        -n '__fish_seen_subcommand_from playlist-list show-list playlist-export titles-export playlist-build' \
        -d 'Rewrite exported paths onto this prefix'
    complete -c $prog -rF -s u -l update -n '__fish_seen_subcommand_from metadata' \
        -d 'Change the item to match a JSON file'
    complete -c $prog -rF -l m3u \
        -n '__fish_seen_subcommand_from playlist-list show-list playlist-build' \
        -d 'Also export an M3U file using Plex server paths'
    complete -c $prog -x -l album -n '__fish_seen_subcommand_from library-list titles-export' \
        -a '(__plexdo_albums 0)' -d 'Restrict to a single photo album'
    complete -c $prog -x -s t -l type -n '__fish_seen_subcommand_from library-list' \
        -a 'album artist clip collection episode folder movie photo season show track' -d 'What to list'
    complete -c $prog -x -l path -n '__fish_seen_subcommand_from library-list' \
        -d 'With --type folder, the folder to list'
    complete -c $prog -x -l filter -n '__fish_seen_subcommand_from library-list' \
        -d 'List only what matches FIELD=VALUE'
    complete -c $prog -x -l category -n '__fish_seen_subcommand_from library-list' \
        -d 'Short for --filter genre=CATEGORY'
    complete -c $prog -l list-categories -n '__fish_seen_subcommand_from library-list' \
        -d 'List the genres of the type listed'
    complete -c $prog -x -l sort -n '__fish_seen_subcommand_from titles-export' \
        -a 'alpha date random' -d 'Sort order'
    complete -c $prog -x -l media-type -n '__fish_seen_subcommand_from search' \
        -a 'movie show episode track photo album artist' -d 'Restrict to one media type'
    complete -c $prog -x -l library-id -n '__fish_seen_subcommand_from search' \
        -a '(__plexdo_libraries)' -d 'Restrict to one library'
    complete -c $prog -x -l section -n '__fish_seen_subcommand_from status' -a 'server sessions users accounts connections scans activities tasks' -d 'Show only one section'
    complete -c $prog -s a -l all -n '__fish_seen_subcommand_from rescan' -d 'Rescan every library'
    complete -c $prog -s s -l status -n '__fish_seen_subcommand_from rescan' -d 'Print all active scan jobs'
    complete -c $prog -s n -l now -n '__fish_seen_subcommand_from rescan' -d 'Cancel pending scans first'
    complete -c $prog -s o -l overwrite \
        -n '__fish_seen_subcommand_from playlist-copy playlist-build' \
        -d 'Replace an existing playlist of the same name'
    complete -c $prog -s o -l overwrite -n '__fish_seen_subcommand_from write-config-example' \
        -d 'Replace an existing config file'
    complete -c $prog -s o -l overwrite -n '__fish_seen_subcommand_from write-secrets-example' \
        -d 'Replace an existing secrets file'
    complete -c $prog -s I -l interleaved -n '__fish_seen_subcommand_from playlist-build' \
        -d 'Take one episode from each show in turn'
    complete -c $prog -s C -l chronological -n '__fish_seen_subcommand_from playlist-build' \
        -d 'Sort the episodes and movies by air date'
    complete -c $prog -s R -l randomize -n '__fish_seen_subcommand_from playlist-build' \
        -d 'Shuffle an existing playlist into a new one'
    complete -c $prog -s A -l append -n '__fish_seen_subcommand_from playlist-build' \
        -d 'Add items to the end of an existing playlist'
    complete -c $prog -s M -l merge -n '__fish_seen_subcommand_from playlist-build' \
        -d 'Mix two existing playlists into a new one'
    complete -c $prog -s A -l all -n '__fish_seen_subcommand_from playlist-copy' \
        -d 'Copy to every user the server is shared with'
    complete -c $prog -s T -l to -n '__fish_seen_subcommand_from playlist-copy' \
        -d 'Copy to one user, under a title of your choosing'
    complete -c $prog -x -l ratio -n '__fish_seen_subcommand_from playlist-build; and __plexdo_mode merge' \
        -d 'A:B: take A items from the first, then B from the second'
    complete -c $prog -s s -l stop-short -n '__fish_seen_subcommand_from playlist-build; and __plexdo_mode merge' \
        -d 'Stop when either playlist runs out'
    complete -c $prog -s U -l unique -n '__fish_seen_subcommand_from playlist-build; and __plexdo_mode merge' \
        -d 'Skip an item already taken'
    complete -c $prog -x -s u -l user -n '__fish_seen_subcommand_from playlist-build' \
        -a '(__plexdo_users)' -d 'Create the playlist for this user instead'
    complete -c $prog -s a -l all-users -n '__fish_seen_subcommand_from playlist-build' \
        -d 'Create the playlist for every user on the server'
    complete -c $prog -x -s s -l session -n '__fish_seen_subcommand_from wait' -d 'Follow the session with this sessionKey'
    complete -c $prog -x -s r -l rating-key -n '__fish_seen_subcommand_from wait' \
        -a '(__plexdo_rating_keys)' -d 'Wait for this video'
    complete -c $prog -x -s i -l interval -n '__fish_seen_subcommand_from wait' -d 'Seconds between polls'
    complete -c $prog -x -l fast-interval -n '__fish_seen_subcommand_from wait' -d 'Seconds between polls near the end point'
    complete -c $prog -l no-credits -n '__fish_seen_subcommand_from wait' -d 'Ignore the credits marker and wait for the end'
    complete -c $prog -x -l offset -n '__fish_seen_subcommand_from wait' -d 'Signed seconds: negative ends early, positive sleeps after'
    complete -c $prog -l now -n '__fish_seen_subcommand_from wait' -d 'With -r: exit at once if the video is not playing'
    complete -c $prog -x -l port -n '__fish_seen_subcommand_from player-remote-play' -d 'Port the player listens on for remote control'
    complete -c $prog -x -l player-user -n '__fish_seen_subcommand_from player-remote-play' -d 'Account signed in to the player: user id, username, or email'
    complete -c $prog -x -l server-url -n '__fish_seen_subcommand_from player-remote-play' -d 'Server address the player should fetch from'
    complete -c $prog -s a -l all -n '__fish_seen_subcommand_from wait' -d 'Wait for every play by every user'
    complete -c $prog -x -l paused -n '__fish_seen_subcommand_from wait' -d 'Count a play as over once paused this many seconds'
    complete -c $prog -l one-way -n '__fish_seen_subcommand_from show-watched-cp' -d 'Only write to the second user'
    complete -c $prog -x -s l -l library -n '__fish_seen_subcommand_from show-watched-cp' \
        -a '(__plexdo_libraries)' -d 'Restrict to one library'
    complete -c $prog -x -s t -l title -n '__fish_seen_subcommand_from show-watched-cp' \
        -a '(__plexdo_rating_keys)' -d 'Restrict to one item'
    complete -c $prog -l unwatch -n '__fish_seen_subcommand_from show-watched-cp' -d 'Propagate the unwatched state instead'
    complete -c $prog -x -s u -l username -n '__fish_seen_subcommand_from login' -d 'Plex username or email'
    complete -c $prog -x -s p -l password -n '__fish_seen_subcommand_from login' -d 'Plex password (INSECURE: visible in ps)'
    complete -c $prog -l save-password -n '__fish_seen_subcommand_from login' -d 'Also save the password in the system keyring'
    complete -c $prog -x -s c -l code -n '__fish_seen_subcommand_from login' -d 'Two-factor authentication code'
    complete -c $prog -s 2 -l two-factor -n '__fish_seen_subcommand_from login' -d 'Prompt for a two-factor code'
    complete -c $prog -x -s u -l username -n '__fish_seen_subcommand_from logout' -d 'Sign out only this saved name'
    complete -c $prog -l remove -n '__fish_seen_subcommand_from set-pin' -d 'Remove the saved PIN instead of prompting'
end
