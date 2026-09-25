# SPDX-License-Identifier: GPL-3.0-or-later
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
    '--prefix', '--throttle', '-p', '-l', '--library', '-t', '--title', '-u', '--username',
    '-c', '--code', '-f', '--format'
)

$script:PlexdoCommands = [ordered]@{
    'list-libraries'          = 'List all Plex libraries'
    'list-titles'             = 'List titles in a library'
    'list-library'            = 'List titles in a library (alias for list-titles)'
    'list-show'               = 'List all episodes in a show'
    'export-titles'           = 'Export a library to M3U or an HTML gallery'
    'search'                  = 'Search Plex for titles matching a query'
    'list-users'              = 'List all managed/home users'
    'list-playlists'          = 'List playlists for a user'
    'list-playlist'           = 'List items in a specific playlist'
    'export-playlist'         = 'Export a playlist to an M3U file'
    'clean-playlist'          = 'Remove watched items from a playlist'
    'remove-playlist'         = 'Delete a playlist from a user'
    'append-playlist'         = 'Append items to an existing playlist'
    'show-metadata'           = 'Display metadata for a single item'
    'read'                    = 'Stream a media file to stdout'
    'rescan'                  = 'Trigger a library rescan or show scan status'
    'status'                  = 'Show server identity, sessions, users, and tasks'
    'find-missing'            = 'Find gaps in episode numbering across every show'
    'build-interleaved'       = 'Round-robin playlist from shows'
    'build-chronological'     = 'Date-sorted playlist from shows and movies'
    'build-randomize'         = 'Randomize a playlist into a new one'
    'build-concatenated'      = 'Join several playlists end to end into one'
    'copy-playlist-all-users' = 'Copy a playlist to all managed users'
    'copy-playlist-to-user'   = 'Copy a playlist to a specific user'
    'copy-watched'            = 'Synchronise watched state between two users'
    'login'                   = 'Authenticate with plex.tv and save a token'
    'write-config-example'    = 'Write a template config file'
}

$script:PlexdoGlobalFlags = [ordered]@{
    '--format'  = 'Output format: table, json, yaml, csv, clixml'
    '--json'    = 'Shorthand for --format json'
    '--verbose' = 'Print high-level progress to stderr'
    '--debug'   = 'Print detailed internal logs to stderr'
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
    foreach ($row in Get-PlexdoCacheRows 'users' @('list-users')) {
        $results += New-PlexdoResult ([string] $row.id) $row.title
        if ($row.title) { $results += New-PlexdoResult ([string] $row.title) "user id $($row.id)" }
    }
    return $results
}

function Get-PlexdoLibraries {
    $results = @()
    foreach ($row in Get-PlexdoCacheRows 'libraries' @('list-libraries')) {
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
            Update-PlexdoCache @('list-titles', $library)
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
    foreach ($row in Get-PlexdoCacheRows "playlists.$User" @('list-playlists', $User)) {
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
    foreach ($row in Get-PlexdoCacheRows "titles.$Library" @('list-titles', $Library)) {
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

    $command = $tokens | Where-Object { -not $_.StartsWith('-') } | Select-Object -First 1
    $previous = if ($tokens.Count) { $tokens[-1] } else { '' }
    $positionals = Get-PlexdoPositionals $tokens
    $index = $positionals.Count

    $results = @()

    # A value expected by the option just typed.
    switch ($previous) {
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
                '^(list-playlist|list-show|build-)' { $flags['--m3u'] = 'Also export an M3U file'; $flags['--prefix'] = 'Rewrite exported paths onto this prefix' }
                '^(export-playlist|export-titles)$' { $flags['--prefix'] = 'Rewrite exported paths onto this prefix' }
                '^(build-|copy-playlist-)'          { $flags['--overwrite'] = 'Replace an existing playlist of the same name' }
                '^build-concatenated$'              { $flags['--unique'] = 'Skip an item an earlier playlist already contributed' }
                '^(list-titles|list-library|export-titles)$' { $flags['--album'] = 'Restrict to a single photo album' }
                '^export-titles$'                   { $flags['--sort'] = 'Sort order' }
                '^search$'                          { $flags['--media-type'] = 'Restrict to one media type'; $flags['--library-id'] = 'Restrict to one library' }
                '^rescan$'                          { $flags['--status'] = 'Print all active scan jobs'; $flags['--now'] = 'Cancel pending scans first' }
                '^status$'                          { $flags['--section'] = 'Show only one section' }
                '^find-missing$'                    { $flags['--library'] = 'Library to look in'; $flags['--all'] = 'Check every show'; $flags['--season'] = 'Season number, or several comma separated'; $flags['--include-specials'] = 'Also check season 0' }
                '^clean-playlist$'                  { $flags['--include-partial'] = 'Also remove part-played items' }
                '^copy-watched$'                    { $flags['--one-way'] = 'Only write to the second user'; $flags['--library'] = 'Restrict to one library'; $flags['--title'] = 'Restrict to one item'; $flags['--unwatch'] = 'Propagate the unwatched state instead' }
                '^login$'                           { $flags['--username'] = 'Plex username or email'; $flags['--password'] = 'Plex password (INSECURE)'; $flags['--code'] = 'Two-factor code'; $flags['--two-factor'] = 'Prompt for a two-factor code' }
            }
            $results = $flags.GetEnumerator() | ForEach-Object { New-PlexdoResult $_.Key $_.Value }
        } else {
            $user = if ($positionals.Count) { $positionals[0] } else { '' }
            switch ($command) {
                { $_ -in 'list-titles', 'list-library' } { if ($index -eq 0) { $results = Get-PlexdoLibraries } }
                'export-titles'  { if ($index -eq 0) { $results = Get-PlexdoLibraries } }
                'rescan'         { if ($index -eq 0) { $results = Get-PlexdoLibraries } }
                'find-missing'   { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'read'           { if ($index -eq 0) { $results = Get-PlexdoLibraries }
                                   elseif ($index -eq 1) { $results = Get-PlexdoRatingKeys } }
                'list-show'      { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'show-metadata'  { if ($index -eq 0) { $results = Get-PlexdoRatingKeys } }
                'list-playlists' { if ($index -eq 0) { $results = Get-PlexdoUsers } }
                'search'         { if ($index -eq 0) { $results = Get-PlexdoUsers } }
                'list-playlist'  { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                   elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user -IncludeKeys } }
                'export-playlist'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'remove-playlist'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'clean-playlist'    { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'append-playlist'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user }
                                      else { $results = Get-PlexdoRatingKeys } }
                'build-randomize'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                      elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'build-concatenated' { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                       elseif ($index -ge 2) { $results = Get-PlexdoPlaylists $user -IncludeKeys } }
                'copy-playlist-all-users' { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                            elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user } }
                'copy-playlist-to-user'   { if ($index -eq 0) { $results = Get-PlexdoUsers }
                                            elseif ($index -eq 1) { $results = Get-PlexdoPlaylists $user }
                                            elseif ($index -eq 2) { $results = Get-PlexdoUsers } }
                'copy-watched'   { if ($index -le 1) { $results = Get-PlexdoUsers } }
                { $_ -in 'build-interleaved', 'build-chronological' } {
                                   if ($index -ge 1) { $results = Get-PlexdoRatingKeys } }
            }
        }
    }

    $results | Where-Object { $_.ListItemText -like "$wordToComplete*" }
}
