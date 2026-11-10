# SPDX-FileCopyrightText: 2026 SidusNare
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileContributor: Claude Opus 5.5 (AI-generated)
#
#
# PowerShell completion for plexdo.
#
# Installation:
#   Current session:  . ./plexdo.ps1
#   Permanently:      Add-Content $PROFILE ". <path>\plexdo.ps1"
#                     (create the profile first if needed:
#                      New-Item -Type File -Force $PROFILE)
#
# Completion for user and library IDs and titles, rating keys, playlists, and
# photo albums is read from the cache plexdo writes as a side effect of its
# list commands. A stale cache is refreshed in the background, so completion
# never blocks; the values offered are whatever is cached at that moment.

$script:PlexdoCacheTtl = 900
$script:PlexdoCacheDir = $null

# Options that consume the following token, so it is not counted as positional.
$script:PlexdoValueOptions = @(
    '--m3u', '--album', '--sort', '--media-type', '--library-id', '--section',
    '--prefix', '--throttle', '-p', '-l', '--library', '-t', '--title', '-u', '--user',
    '--username', '--port', '--player-user', '--server-url', '--ratio', '--debug-log',
    '-c', '--code', '-f', '--format'
)

$script:PlexdoCommands = [ordered]@{
    'album-list'            = 'Show one album with its played state and progress'
    'albums-list'           = 'List the albums in a music or photo library'
    'libraries-list'        = 'List the server''s libraries'
    'library-list'          = 'List the titles in a library'
    'login'                 = 'Sign in to plex.tv and save the token'
    'logout'                = 'Sign out of plex.tv and remove the saved tokens'
    'merge-build'           = 'Mix two playlists into a new one at a ratio'
    'missing-find'          = 'Find gaps in the episode numbering of a show'
    'player-remote-play'    = 'Tell a player, reached directly, to play an item'
    'playlist-build'        = 'Build a playlist, or add items to one'
    'playlist-clean'        = 'Remove the watched items from a playlist'
    'playlist-copy'         = 'Copy a playlist to one user, or to all of them'
    'playlist-export'       = 'Export a playlist to an M3U file'
    'playlist-list'         = 'List the items in a playlist'
    'playlist-remove'       = 'Delete a playlist'
    'playlists-list'        = 'List a user''s playlists'
    'read'                  = 'Stream a media file to stdout'
    'rescan'                = 'Rescan libraries, or show the scans under way'
    'search'                = 'Search for titles matching a query'
    'set-pin'               = 'Save or remove a Plex Home member''s PIN'
    'show-list'             = 'List a show''s episodes'
    'show-metadata'         = 'Show the metadata of one item'
    'show-watched-cp'       = 'Sync watched state and resume points of two users'
    'status'                = 'Show the server''s sessions, users, scans, and tasks'
    'titles-export'         = 'Export a library to an M3U file or photo gallery'
    'users-list'            = 'List the server''s users'
    'wait'                  = 'Sleep until a session''s current play is over'
    'write-config-example'  = 'Write a template configuration file'
    'write-secrets-example' = 'Write an example secrets file, or print it'
}

$script:PlexdoGlobalFlags = [ordered]@{
    '--format'  = 'Output format: table, json, yaml, csv, clixml'
    '--json'    = 'Shorthand for --format json'
    '--verbose' = 'Print high-level progress to stderr'
    '--debug'   = 'Print detailed internal logs to stderr'
    '--debug-log' = 'Append the debug logs, profiled and timestamped, to a file'
    '--dry-run' = 'Show what would happen without mutating Plex'
    '--wide'    = 'Do not shrink table columns to the terminal width'
    '--throttle' = 'Seconds between requests in per-item operations; 0 disables'
    '--version' = 'Show the installed version and exit'
    '--help'    = 'Show help and exit'
}

function Get-PlexdoCacheDir {
    <#
    .SYNOPSIS
        Resolve the completion cache directory, honouring [plex] cache_dir.
    .DESCRIPTION
        Memoised: this reads the configuration file, and doing so once per
        completion candidate would be wasteful.
    #>
    if ($script:PlexdoCacheDir) { return $script:PlexdoCacheDir }

    $windows = $IsWindows -or ($env:OS -eq 'Windows_NT')
    if ($windows) {
        $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA }
                elseif ($env:APPDATA)  { $env:APPDATA }
                else { Join-Path $HOME 'AppData/Local' }
        $app     = Join-Path $base 'PlexDo'
        $config  = Join-Path $app 'plexdo.ini'
        $fallback = Join-Path $app 'Cache'
    } else {
        $config   = Join-Path $HOME '.local/etc/plexdo.ini'
        $fallback = Join-Path $HOME '.cache/plexdo'
    }

    $resolved = $null
    if (Test-Path -LiteralPath $config) {
        $section = ''
        foreach ($line in Get-Content -LiteralPath $config -ErrorAction SilentlyContinue) {
            $trimmed = $line.Trim()
            if ($trimmed -match '^\[(.+)\]$') { $section = $Matches[1]; continue }
            if ($section -eq 'plex' -and $trimmed -match '^cache_dir\s*=\s*(.+)$') {
                $resolved = $Matches[1].Trim()
            }
        }
    }

    if ($resolved) {
        # %VAR% on Windows, $VAR everywhere, and a leading ~.
        $resolved = [Environment]::ExpandEnvironmentVariables($resolved)
        $resolved = [regex]::Replace($resolved, '\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?', {
            param($m)
            $value = [Environment]::GetEnvironmentVariable($m.Groups[1].Value)
            if ($value) { $value } else { $m.Value }
        })
        if ($resolved.StartsWith('~')) { $resolved = Join-Path $HOME $resolved.Substring(1).TrimStart('/', '\') }
        $script:PlexdoCacheDir = $resolved
    } else {
        $script:PlexdoCacheDir = $fallback
    }
    return $script:PlexdoCacheDir
}

function Test-PlexdoCacheFresh {
    <#
    .SYNOPSIS
        True when the cache file exists and is under 15 minutes old.
    #>
    param([string] $Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    $age = (Get-Date) - (Get-Item -LiteralPath $Path).LastWriteTime
    return $age.TotalSeconds -lt $script:PlexdoCacheTtl
}

function Update-PlexdoCache {
    <#
    .SYNOPSIS
        Repopulate a cache in the background, purely for its side effect.
    #>
    param([string[]] $Arguments)
    if (-not (Get-Command plexdo -ErrorAction SilentlyContinue)) { return }
    try {
        Start-Job -ScriptBlock {
            param($cmdArgs)
            & plexdo @cmdArgs *> $null
        } -ArgumentList (, $Arguments) | Out-Null
    } catch {
        # A background refresh is a convenience; never let it break completion.
    }
}

function Get-PlexdoCacheRows {
    <#
    .SYNOPSIS
        Read one cache file, refreshing it in the background when stale.
    #>
    param([string] $Name, [string[]] $RefreshWith)
    $path = Join-Path (Get-PlexdoCacheDir) "$Name.json"
    if (-not (Test-PlexdoCacheFresh $path) -and $RefreshWith) {
        Update-PlexdoCache $RefreshWith
    }
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    try {
        return @(Get-Content -LiteralPath $path -Raw | ConvertFrom-Json)
    } catch {
        return @()
    }
}

function New-PlexdoResult {
    <#
    .SYNOPSIS
        Build a completion result, quoting values that contain spaces.
    #>
    param([string] $Value, [string] $Tooltip)
    $insert = if ($Value -match '\s') { "'" + $Value.Replace("'", "''") + "'" } else { $Value }
    if (-not $Tooltip) { $Tooltip = $Value }
    [System.Management.Automation.CompletionResult]::new(
        $insert, $Value, 'ParameterValue', $Tooltip)
}

function Get-PlexdoPositionals {
    <#
    .SYNOPSIS
        The positional arguments typed after the subcommand.
    .DESCRIPTION
        Options that take a value swallow the following token, so it is not
        mistaken for a positional and the argument indexes stay correct.
    #>
    param([string[]] $Tokens)
    $positionals = @()
    $seenCommand = $false
    $skipNext = $false
    foreach ($token in $Tokens) {
        if ($skipNext) { $skipNext = $false; continue }
        if ($script:PlexdoValueOptions -contains $token) { $skipNext = $true; continue }
        if ($token.StartsWith('-')) { continue }
        if (-not $seenCommand) { $seenCommand = $true; continue }
        $positionals += $token
    }
    return , $positionals
}

function Get-PlexdoUsers {
    $results = @(New-PlexdoResult '0' 'admin account')
    foreach ($row in Get-PlexdoCacheRows 'users' @('users-list')) {
        $results += New-PlexdoResult ([string] $row.id) $row.title
        if ($row.title) { $results += New-PlexdoResult ([string] $row.title) "user id $($row.id)" }
    }
    return $results
}

function Get-PlexdoLibraries {
    $results = @()
    foreach ($row in Get-PlexdoCacheRows 'libraries' @('libraries-list')) {
        $results += New-PlexdoResult ([string] $row.id) $row.title
        if ($row.title) { $results += New-PlexdoResult ([string] $row.title) "library id $($row.id)" }
    }
    return $results
}

function Get-PlexdoRatingKeys {
    # Only the key is insertable: a ratingKey is numeric, so the title is
    # shown to identify the item rather than to be typed.
    $results = @()
    $dir = Get-PlexdoCacheDir
    if (-not (Test-Path -LiteralPath $dir)) { return $results }
    foreach ($file in Get-ChildItem -LiteralPath $dir -Filter 'titles.*.json' -ErrorAction SilentlyContinue) {
        $library = $file.BaseName -replace '^titles\.', ''
        if (-not (Test-PlexdoCacheFresh $file.FullName)) {
            Update-PlexdoCache @('library-list', $library)
        }
        try {
            foreach ($row in @(Get-Content -LiteralPath $file.FullName -Raw | ConvertFrom-Json)) {
                $results += New-PlexdoResult ([string] $row.ratingKey) $row.title
            }
        } catch { }
    }
    return $results
}

function Get-PlexdoPlaylists {
    param([string] $User, [switch] $IncludeKeys)
    if (-not $User) { $User = '0' }
    $results = @()
    foreach ($row in Get-PlexdoCacheRows "playlists.$User" @('playlists-list', $User)) {
        $results += New-PlexdoResult ([string] $row.title) "$($row.items) items"
        if ($IncludeKeys) {
            $results += New-PlexdoResult ([string] $row.ratingKey) $row.title
        }
    }
    return $results
}

function Get-PlexdoAlbums {
    param([string] $Library)
    if (-not $Library) { return @() }
    $seen = @{}
    $results = @()
    foreach ($row in Get-PlexdoCacheRows "titles.$Library" @('library-list', $Library)) {
        $album = ([string] $row.title -split ' - ')[0]
        if ($album -and -not $seen.ContainsKey($album)) {
            $seen[$album] = $true
            $results += New-PlexdoResult $album 'photo album'
        }
    }
    return $results
}

Register-ArgumentCompleter -Native -CommandName plexdo -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)

    $tokens = @($commandAst.CommandElements | Select-Object -Skip 1 |
                ForEach-Object { $_.ToString() })
    # The word being typed is not yet a settled argument. Note that a range
    # of 0..-1 wraps in PowerShell and would return the whole array, so the
    # single-token case is handled separately.
    if ($wordToComplete -and $tokens.Count -and $tokens[-1] -eq $wordToComplete) {
        $tokens = if ($tokens.Count -le 1) { @() } else { $tokens[0..($tokens.Count - 2)] }
    }

    # The first token that is neither an option nor an option's value.
    $command = $null
    $skipNext = $false
    foreach ($token in $tokens) {
        if ($skipNext) { $skipNext = $false; continue }
        if ($script:PlexdoValueOptions -contains $token) { $skipNext = $true; continue }
        if (-not $token.StartsWith('-')) { $command = $token; break }
    }
    $previous = if ($tokens.Count) { $tokens[-1] } else { '' }
    $positionals = Get-PlexdoPositionals $tokens
    $index = $positionals.Count

    # playlist-build and playlist-copy take a flag saying what their positional
    # arguments are. The comparisons are case-sensitive: -a is --all-users.
    $mode = ''
    foreach ($token in $tokens) {
        if ($token -cin '-I', '--interleaved') { $mode = 'interleaved'; break }
        if ($token -cin '-C', '--chronological') { $mode = 'chronological'; break }
        if ($token -cin '-R', '--randomize') { $mode = 'randomize'; break }
        if ($token -cin '-A', '--append', '--all') { $mode = 'all-or-append'; break }
        if ($token -cin '-T', '--to') { $mode = 'to'; break }
    }

    $results = @()

    # A value expected by the option just typed.
    switch ($previous) {
        { $_ -in '-u', '--user' } {
            if ($command -in 'playlist-build', 'merge-build') { $results = Get-PlexdoUsers }
        }
        { $_ -in '-r', '--rating-key' } {
            if ($command -eq 'wait') { $results = Get-PlexdoRatingKeys }
        }
        { $_ -in '-f', '--format' } {
            $results = @('table', 'json', 'yaml', 'csv', 'clixml') |
                ForEach-Object { New-PlexdoResult $_ 'output format' }
        }
        '--sort' {
            $results = @('alpha', 'date', 'random') |
                ForEach-Object { New-PlexdoResult $_ 'sort order' }
        }
        '--media-type' {
            $results = @('movie', 'show', 'episode', 'track', 'photo', 'album', 'artist') |
                ForEach-Object { New-PlexdoResult $_ 'media type' }
        }
        '--section' {
            $results = @('server', 'sessions', 'users', 'accounts', 'connections',
                         'scans', 'activities', 'tasks') |
                ForEach-Object { New-PlexdoResult $_ 'status section' }
        }
        '--album' {
            # Albums come from the library named in the first positional. A
            # parenthesised `if` is not a valid argument expression in
            # PowerShell, so the value is bound first.
            $albumLibrary = if ($positionals.Count) { $positionals[0] } else { '' }
            $results = Get-PlexdoAlbums $albumLibrary
        }
        '--library-id' { $results = Get-PlexdoLibraries }
        { $_ -in '-l', '--library' } { $results = Get-PlexdoLibraries }
        { $_ -in '-t', '--title' } { $results = Get-PlexdoRatingKeys }
    }

    if (-not $results) {
        if (-not $command) {
            # No subcommand yet.
            $results = $script:PlexdoCommands.GetEnumerator() |
                ForEach-Object { New-PlexdoResult $_.Key $_.Value }
        } elseif ($wordToComplete.StartsWith('-')) {
            $flags = [ordered]@{} + $script:PlexdoGlobalFlags
            switch -Regex ($command) {
                '^(playlist-list|show-list|playlist-build|merge-build)$' { $flags['--m3u'] = 'Also export an M3U file'; $flags['--prefix'] = 'Rewrite exported paths onto this prefix' }
                '^(playlist-export|titles-export)$' { $flags['--prefix'] = 'Rewrite exported paths onto this prefix' }
                '^(playlist-build|merge-build|playlist-copy)$' { $flags['--overwrite'] = 'Replace an existing playlist of the same name' }
                '^(playlist-build|merge-build)$'    { $flags['--user'] = 'Create the playlist for this user instead'; $flags['--all-users'] = 'Create the playlist for every user on the server' }
                '^playlist-build$'                  { $flags['--interleaved'] = 'Take one episode from each show in turn'; $flags['--chronological'] = 'Sort the episodes and movies by air date'; $flags['--randomize'] = 'Shuffle an existing playlist into a new one'; $flags['--append'] = 'Add items to the end of an existing playlist' }
                '^playlist-copy$'                   { $flags['--all'] = 'Copy to every user the server is shared with'; $flags['--to'] = 'Copy to one user, under a title of your choosing' }
                '^merge-build$'                     { $flags['--ratio'] = 'A:B: take A items from the first, then B from the second'; $flags['--stop-short'] = 'Stop when either playlist runs out'; $flags['--unique'] = 'Skip an item already taken' }
                '^(library-list|titles-export)$'    { $flags['--album'] = 'Restrict to a single photo album' }
                '^titles-export$'                   { $flags['--sort'] = 'Sort order' }
                '^search$'                          { $flags['--media-type'] = 'Restrict to one media type'; $flags['--library-id'] = 'Restrict to one library' }
                '^rescan$'                          { $flags['--status'] = 'Print all active scan jobs'; $flags['--now'] = 'Cancel pending scans first' }
                '^status$'                          { $flags['--section'] = 'Show only one section' }
                '^write-config-example$'            { $flags['--overwrite'] = 'Replace an existing config file' }
                '^write-secrets-example$'           { $flags['--overwrite'] = 'Replace an existing secrets file' }
                '^wait$'                            { $flags['--session'] = 'Follow the session with this sessionKey'; $flags['--rating-key'] = 'Wait for this video'; $flags['--interval'] = 'Seconds between polls'; $flags['--fast-interval'] = 'Seconds between polls near the end point'; $flags['--no-credits'] = 'Ignore the credits marker and wait for the end'; $flags['--offset'] = 'Signed seconds: negative ends early, positive sleeps after'; $flags['--all'] = 'Wait for every play by every user'; $flags['--paused'] = 'Count a play as over once paused this many seconds'; $flags['--now'] = 'With -r: exit at once if the video is not playing' }
                '^player-remote-play$'              { $flags['--port'] = 'Port the player listens on for remote control'; $flags['--player-user'] = 'Account signed in to the player: user id, username, or email'; $flags['--server-url'] = 'Server address the player should fetch from' }
                '^missing-find$'                    { $flags['--library'] = 'Library to look in'; $flags['--all'] = 'Check every show'; $flags['--season'] = 'Season number, or several comma separated'; $flags['--include-specials'] = 'Also check season 0' }
                '^playlist-clean$'                  { $flags['--include-partial'] = 'Also remove part-played items' }
                '^show-watched-cp$'                    { $flags['--one-way'] = 'Only write to the second user'; $flags['--library'] = 'Restrict to one library'; $flags['--title'] = 'Restrict to one item'; $flags['--unwatch'] = 'Propagate the unwatched state instead' }
                '^login$'                           { $flags['--username'] = 'Plex username or email'; $flags['--password'] = 'Plex password (INSECURE)'; $flags['--save-password'] = 'Also save the password in the system keyring'; $flags['--code'] = 'Two-factor code'; $flags['--two-factor'] = 'Prompt for a two-factor code' }
                '^logout$'                          { $flags['--username'] = 'Sign out only this saved name' }
                '^set-pin$'                         { $flags['--remove'] = 'Remove the saved PIN instead of prompting' }
            }
            $results = $flags.GetEnumerator() | ForEach-Object { New-PlexdoResult $_.Key $_.Value }
        } else {
            $user = if ($positionals.Count) { $positionals[0] } else { '' }
            switch ($command) {
                { $_ -in 'library-list', 'albums-list' } { if ($index -eq 0) { $results = Get-PlexdoLibraries } }
                'titles-export'  { if ($index -eq 0) { $results = Get-PlexdoLibraries } }
                'rescan'         { if ($index -eq 0) { $results = Get-PlexdoLibraries } }
                'missing-find'   { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'read'           { if ($index -eq 0) { $results = Get-PlexdoLibraries }
                                   elseif ($index -eq 1) { $results = Get-PlexdoRatingKeys } }
                'show-list'      { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'player-remote-play' { if ($index -eq 1) { $results = Get-PlexdoRatingKeys } }
                'show-metadata'  { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'album-list'     { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'playlists-list' { if ($index -eq 0) { $results = Get-PlexdoUsers } }
                'search'         { if ($index -eq 0) { $results = Get-PlexdoUsers } }
                'set-pin'        { if ($index -eq 0) { $results = Get-PlexdoUsers } }
                'playlist-list'  { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                   elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user -IncludeKeys } }
                'playlist-export'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'playlist-remove'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'playlist-clean'    { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'playlist-build'    {
                    if ($mode -in 'interleaved', 'chronological') {
                        if ($index -ge 1) { $results = Get-PlexdoRatingKeys }
                    } elseif ($mode -in 'randomize', 'all-or-append') {
                        if ($index -eq 0) { $results = Get-PlexdoUsers }
                        elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user -IncludeKeys }
                        elseif ($mode -eq 'all-or-append') { $results = Get-PlexdoRatingKeys }
                    }
                }
                'merge-build'       { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -in 2, 3) { $results = Get-PlexdoPlaylists $user -IncludeKeys } }
                'playlist-copy'     { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user }
                                      elseif ($index -eq 2 -and $mode -eq 'to') { $results = Get-PlexdoUsers } }
                'show-watched-cp'   { if ($index -le 1) { $results = Get-PlexdoUsers } }
            }
        }
    }

    $results | Where-Object { $_.ListItemText -like "$wordToComplete*" }
}
